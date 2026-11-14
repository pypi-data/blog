"""Check how each PyPI project imports standard-library modules removed in Python 3.12 and 3.13.

The py-code.org index records that a project imports, say, `imp`, but not whether the import
is guarded. This script downloads the same release file the index scanned, finds every
import of a removed module, and records its context:

- fallback: inside an `except` block (runs only if the code in `try:` failed)
- guarded:  inside `try:` with an ImportError / ModuleNotFoundError / Exception / bare handler
- gated:    inside an `if` (or `else` of an `if`) whose test reads `sys.version_info`,
            `sys.version`, `PY2`/`PY3`-style flags or `platform.python_version`
- function: inside a function or method body, not guarded (fails when that code runs)
- module:   at module level, not guarded (fails when the file is imported)

It also notes whether the file is a test, setup or docs/example file, and the release's
Requires-Dist (to spot backports such as legacy-cgi or audioop-lts).

Usage: removed_check.py <projects.tsv> <out.jsonl> [--workers N]
projects.tsv: project<TAB>version<TAB>file, one per line. Already-done projects are skipped.
"""
import ast
import io
import json
import sys
import tarfile
import threading
import time
import warnings
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed

warnings.filterwarnings("ignore", category=SyntaxWarning)

import requests

UA = "py-code.org-blog/0.1 (removed stdlib modules check)"
REMOVED_312 = ["asynchat", "asyncore", "distutils", "imp", "smtpd"]
REMOVED_313 = [
    "aifc", "audioop", "cgi", "cgitb", "chunk", "crypt", "imghdr", "lib2to3", "mailcap",
    "msilib", "nis", "nntplib", "ossaudiodev", "pipes", "sndhdr", "spwd", "sunau",
    "telnetlib", "uu", "xdrlib",
]
REMOVED = {m: "3.12" for m in REMOVED_312} | {m: "3.13" for m in REMOVED_313}
MAX_TAR = 200 * 1024 * 1024
MAX_PY = 5 * 1024 * 1024
GUARD_EXC = {"ImportError", "ModuleNotFoundError", "Exception", "BaseException"}
VERSION_HINTS = ("version_info", "sys.version", "PY2", "PY3", "PY27", "PY312", "PY313",
                 "python_version", "hexversion", "IS_PY", "PYTHON_VERSION",
                 "py3k", "PY3K", "py3", "PY_3", "is_py3", "IS_PY3")

local = threading.local()


def get(url, **kw):
    if not hasattr(local, "s"):
        local.s = requests.Session()
        local.s.headers["User-Agent"] = UA
    for attempt in range(5):
        try:
            r = local.s.get(url, timeout=60, **kw)
        except requests.RequestException:
            time.sleep(2 ** attempt)
            continue
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(int(r.headers.get("Retry-After", 2 ** attempt)))
            continue
        return r
    raise RuntimeError(f"giving up on {url}")


class RangeFile(io.RawIOBase):
    BLOCK = 256 * 1024

    def __init__(self, url, size):
        self.url, self.size, self.pos, self.cache = url, size, 0, {}

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else self.pos + off if whence == 1 else self.size + off
        return self.pos

    def _block(self, i):
        if i not in self.cache:
            start = i * self.BLOCK
            end = min(start + self.BLOCK, self.size) - 1
            r = get(self.url, headers={"Range": f"bytes={start}-{end}"})
            if r.status_code != 206:
                raise RuntimeError(f"range not supported: {r.status_code}")
            self.cache[i] = r.content
            if len(self.cache) > 64:
                self.cache.pop(next(iter(self.cache)))
        return self.cache[i]

    def readinto(self, b):
        n = min(len(b), self.size - self.pos)
        if n <= 0:
            return 0
        out, pos, need = bytearray(), self.pos, n
        while need:
            blk = self._block(pos // self.BLOCK)
            o = pos % self.BLOCK
            chunk = blk[o:o + need]
            out += chunk
            pos += len(chunk)
            need -= len(chunk)
        b[:n] = out
        self.pos += n
        return n


def _handler_names(h):
    if h.type is None:
        return {"BaseException"}
    nodes = h.type.elts if isinstance(h.type, ast.Tuple) else [h.type]
    out = set()
    for n in nodes:
        if isinstance(n, ast.Name):
            out.add(n.id)
        elif isinstance(n, ast.Attribute):
            out.add(n.attr)
    return out


def _is_version_test(test):
    src = ast.unparse(test)
    return any(h in src for h in VERSION_HINTS)


def find_imports(tree):
    """Yield (module, line, context) for each import of a removed module."""
    out = []

    def walk(node, ctx):
        # ctx: dict with guarded, gated, function flags
        for field, value in ast.iter_fields(node):
            children = value if isinstance(value, list) else [value]
            for child in children:
                if not isinstance(child, ast.AST):
                    continue
                c = dict(ctx)
                if isinstance(node, (ast.Try, getattr(ast, "TryStar", ast.Try))) and field == "handlers":
                    c["fallback"] = True
                if isinstance(node, (ast.Try, getattr(ast, "TryStar", ast.Try))) and field == "body":
                    if any(_handler_names(h) & GUARD_EXC for h in node.handlers):
                        c["guarded"] = True
                if isinstance(node, ast.If) and field in ("body", "orelse"):
                    c["tests"] = c.get("tests", []) + [ast.unparse(node.test)[:120]]
                    if _is_version_test(node.test):
                        c["gated"] = True
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                    c["function"] = True
                if isinstance(child, ast.Import):
                    for a in child.names:
                        top = a.name.split(".")[0]
                        if top in REMOVED:
                            out.append((top, child.lineno, c))
                elif isinstance(child, ast.ImportFrom) and not child.level and child.module:
                    top = child.module.split(".")[0]
                    if top in REMOVED:
                        out.append((top, child.lineno, c))
                walk(child, c)

    walk(tree, {})
    return out


def context_label(c):
    if c.get("fallback"):
        return "fallback"
    if c.get("guarded"):
        return "guarded"
    if c.get("gated"):
        return "gated"
    if c.get("function"):
        return "function"
    return "module"


def file_kind(path):
    p = "/" + path.lower()
    name = p.rsplit("/", 1)[-1]
    if "/test/" in p or "/tests/" in p or "/testing/" in p or name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py":
        return "test"
    if name in ("setup.py", "build.py", "build_ext.py") or "/build_helpers/" in p:
        return "setup"
    if "/docs/" in p or "/doc/" in p or "/examples/" in p or "/example/" in p or "/benchmarks/" in p:
        return "docs"
    return "code"


def strip_root(path, is_sdist):
    if is_sdist and "/" in path:
        path = path.split("/", 1)[1]
    if path.startswith("src/"):
        path = path[4:]
    return path


def own_top_levels(paths):
    tops = set()
    for p in paths:
        if ".dist-info/" in p or ".egg-info/" in p or ".data/" in p:
            continue
        first = p.split("/")[0]
        if first.endswith(".py"):
            first = first[:-3]
        if first.isidentifier():
            tops.add(first)
    return tops


def check(project, version, fname):
    r = get(f"https://pypi.org/pypi/{project}/{version}/json")
    if r.status_code != 200:
        return {"project": project, "error": f"json {r.status_code}"}
    meta = r.json()
    files = [u for u in meta.get("urls", []) if u["filename"] == fname]
    if not files:
        return {"project": project, "error": "file gone"}
    f = files[0]
    members = {}
    if fname.endswith((".whl", ".zip")):
        with zipfile.ZipFile(io.BufferedReader(RangeFile(f["url"], f["size"]), buffer_size=RangeFile.BLOCK)) as z:
            for zi in z.infolist():
                if zi.filename.endswith(".py") and zi.file_size <= MAX_PY:
                    members[zi.filename] = z.read(zi)
    else:
        if f["size"] > MAX_TAR:
            return {"project": project, "error": "sdist too large"}
        with tarfile.open(fileobj=io.BytesIO(get(f["url"]).content), mode="r:*") as t:
            for m in t.getmembers():
                if m.isfile() and m.name.endswith(".py") and m.size <= MAX_PY:
                    members[m.name] = t.extractfile(m).read()
    is_sdist = not fname.endswith(".whl")
    paths = {strip_root(p, is_sdist): p for p in members}
    own = own_top_levels(paths)
    hits = []
    for rel, orig in paths.items():
        try:
            tree = ast.parse(members[orig])
        except (SyntaxError, ValueError):
            continue
        for mod, line, c in find_imports(tree):
            if mod in own:  # the project ships its own module of that name
                continue
            hits.append({"module": mod, "path": rel, "line": line,
                         "context": context_label(c), "kind": file_kind(rel),
                         "tests": c.get("tests", [])})
    return {"project": project, "version": version,
            "requires_dist": meta["info"].get("requires_dist") or [], "hits": hits}


def main():
    src, out = sys.argv[1], sys.argv[2]
    workers = int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 8
    todo = [l.rstrip("\n").split("\t") for l in open(src) if l.strip()]
    done = set()
    try:
        done = {json.loads(l)["project"] for l in open(out)}
    except FileNotFoundError:
        pass
    todo = [t for t in todo if t[0] not in done]
    lock = threading.Lock()
    with open(out, "a") as fh, ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(check, *t): t[0] for t in todo}
        for i, fut in enumerate(as_completed(futs), 1):
            try:
                res = fut.result()
            except Exception as e:  # keep going; record the failure
                res = {"project": futs[fut], "error": repr(e)[:200]}
            with lock:
                fh.write(json.dumps(res) + "\n")
                fh.flush()
            if i % 100 == 0:
                print(f"{i}/{len(todo)}", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
