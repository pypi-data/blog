"""Download every .pth file from the PyPI releases the py-code.org index lists in pth_files.

The index records the path of each .pth file with an `import` line, but not its text. This
script downloads the same release file the index scanned (wheels with HTTP range requests, so
only the .pth members are read), and records for every .pth member (pth_data.py decides from the path whether it runs):

- path:      the path inside the release file
- text:      the file's text (first 20,000 characters)

It also lists any PEP 829 `.start` files in the release (`start`), the replacement for
`import` lines from Python 3.15.

Usage: pth_check.py <projects.tsv> <out.jsonl> [--workers N]
projects.tsv: project<TAB>version<TAB>file, one per line. Already-done projects are skipped.
"""
import io
import json
import sys
import tarfile
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

UA = "py-code.org-blog/0.1 (.pth file check)"
MAX_TAR = 200 * 1024 * 1024
MAX_TEXT = 20_000

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
    """A read-only file over HTTP range requests, so zipfile reads only what it needs."""
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


def check(project, version, fname):
    r = get(f"https://pypi.org/pypi/{project}/{version}/json")
    if r.status_code != 200:
        return {"project": project, "version": version, "error": f"json {r.status_code}"}
    meta = r.json()
    files = [u for u in meta.get("urls", []) if u["filename"] == fname]
    if not files:
        return {"project": project, "version": version, "error": "file gone"}
    f = files[0]
    members, start = {}, []
    if fname.endswith((".whl", ".zip")):
        with zipfile.ZipFile(io.BufferedReader(RangeFile(f["url"], f["size"]), buffer_size=RangeFile.BLOCK)) as z:
            for zi in z.infolist():
                if zi.filename.endswith(".pth"):
                    members[zi.filename] = z.read(zi)
                elif zi.filename.endswith(".start"):
                    start.append(zi.filename)
    else:
        if f["size"] > MAX_TAR:
            return {"project": project, "version": version, "error": "sdist too large"}
        with tarfile.open(fileobj=io.BytesIO(get(f["url"]).content), mode="r:*") as t:
            for m in t.getmembers():
                if m.isfile() and m.name.endswith(".pth"):
                    members[m.name] = t.extractfile(m).read()
                elif m.isfile() and m.name.endswith(".start"):
                    start.append(m.name)
    pth = [{"path": p, "size": len(b),
            "text": b.decode("utf-8", "replace")[:MAX_TEXT]} for p, b in sorted(members.items())]
    return {"project": project, "version": version, "file": fname,
            "upload_time": f.get("upload_time_iso_8601"), "pth": pth, "start": start}


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
