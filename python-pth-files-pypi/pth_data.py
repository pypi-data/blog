"""Numbers for the post on PyPI packages that run code every time Python starts (.pth files).

Reads projects.parquet and pth_files.parquet from the py-code.org dataset, plus checks.jsonl
(written by pth_check.py, which downloads each listed .pth file). Writes pth.json and the
chart SVGs.

Usage: pth_data.py [<parquet-dir>] [<checks.jsonl>] [<out-dir>]

With no arguments it reads the 13 November 2026 snapshot from Hugging Face (pinned
revision), results/checks.jsonl, and writes to ./out.

Where a .pth file ends up decides whether it runs. Python's `site` module reads .pth files
only directly in a site directory:

- every:   at the root of the wheel or of `<name>.data/purelib/` or `.data/platlib/`. pip and uv
           put it in site-packages, so it runs on every Python start in that environment.
- windows: under `<name>.data/data/`, either at its root or in `lib/site-packages/`. The data
           scheme installs relative to the environment's prefix. On Windows the prefix itself
           and `Lib/site-packages` are site directories, so these run there; on Linux and
           macOS they do not.
- never:   anywhere else: inside a package folder, under a path such as `tmp/build-env-…/` that
           was packed by mistake, or in a source distribution (which installs only what its
           build script copies).

What a running .pth does:

- namespace: the boilerplate setuptools writes for pkg_resources-style namespace packages
             (`-nspkg.pth`). It sets up a namespace module and imports no package code.
- own code:  anything else: it imports a module of the package or runs inline code.
"""
import json
import re
import sys
from pathlib import Path

SNAPSHOT = "2026-11-13"
HF_SNAPSHOT = "hf://datasets/pypi-data/py-code@9d81d70d6519d77f4dee4811b3e3a5d88379c17d"
EXEC = ("import ", "import\t")              # site.py runs lines that start with these
DATA_SITE = re.compile(r"^[^/]+\.data/(purelib|platlib)/[^/]+\.pth$")
DATA_WIN = re.compile(r"^[^/]+\.data/data/(lib/site-packages/)?[^/]+\.pth$", re.I)
ENV = re.compile(r"os\.environ|getenv")


def where(path, is_wheel):
    if not is_wheel:
        return "never"
    if "/" not in path or DATA_SITE.match(path):
        return "every"
    if DATA_WIN.match(path):
        return "windows"
    return "never"


def exec_lines(text):
    return [l for l in text.splitlines() if l.startswith(EXEC)]


def kind(text):
    return "namespace" if "sys._getframe(1).f_locals" in text and "types" in text else "own"


def analyse(con, checks):
    projects_all = con.execute("SELECT count(*) FROM p").fetchone()[0]
    listed = {r[0] for r in con.execute("SELECT DISTINCT project FROM t").fetchall()}
    listed_files = con.execute("SELECT count(*) FROM t").fetchone()[0]
    meta = {r[0]: (r[1] or 0, str(r[2])[:10]) for r in con.execute(
        "SELECT project, downloads_30d, upload_time FROM p WHERE project IN (SELECT project FROM t)").fetchall()}
    errors = sorted(p for p in listed if p not in checks or "error" in checks[p])

    files = []
    for p in sorted(listed):
        c = checks.get(p)
        if not c or "error" in c:
            continue
        wheel = c["file"].endswith(".whl")
        for f in c["pth"]:
            lines = exec_lines(f["text"])
            if not lines:
                continue
            files.append({"project": p, "path": f["path"], "where": where(f["path"], wheel),
                          "kind": kind(f["text"]), "env": bool(ENV.search(f["text"])),
                          "first_line": lines[0][:300]})

    def projects(sel):
        return sorted({f["project"] for f in files if sel(f)})

    running = projects(lambda f: f["where"] == "every")
    own = projects(lambda f: f["where"] == "every" and f["kind"] == "own")
    namespace_only = [p for p in projects(lambda f: f["where"] == "every" and f["kind"] == "namespace") if p not in own]
    windows_only = [p for p in projects(lambda f: f["where"] == "windows") if p not in running]
    never = [p for p in sorted({f["project"] for f in files}) if p not in running and p not in windows_only]
    start = sorted(p for p in listed if checks.get(p, {}).get("start"))
    dl = lambda ps: sum(meta[p][0] for p in ps)
    top60k = lambda ps: [p for p in ps if meta[p][0] > 0]
    year = lambda ps, y: sum(1 for p in ps if meta[p][1][:4] == y)
    ns_files = [f for f in files if f["where"] == "every" and f["kind"] == "namespace"]
    ns_py2 = sum(1 for f in ns_files if re.search(r"-py2\.\d+-nspkg\.pth$", f["path"]))

    def row(p):
        fs = [f for f in files if f["project"] == p and f["where"] == "every" and f["kind"] == "own"]
        return {"project": p, "downloads_30d": meta[p][0], "latest_release": meta[p][1],
                "pth": [f["path"] for f in fs], "env": any(f["env"] for f in fs),
                "start": bool(checks[p].get("start")), "first_line": fs[0]["first_line"]}

    own_rows = sorted((row(p) for p in own), key=lambda r: (-r["downloads_30d"], r["project"]))
    return {
        "snapshot": SNAPSHOT,
        "projects_all": projects_all,
        "listed_projects": len(listed),
        "listed_files": listed_files,
        "check_errors": errors,
        "files_with_exec": len(files),
        "files_by_where": {w: sum(1 for f in files if f["where"] == w) for w in ("every", "windows", "never")},
        "running": len(running),
        "running_top60k": len(top60k(running)),
        "running_downloads": dl(running),
        "own": len(own),
        "own_top60k": len(top60k(own)),
        "own_downloads": dl(own),
        "own_env": sum(1 for r in own_rows if r["env"]),
        "own_released_2026": year(own, "2026"),
        "own_start": sum(1 for r in own_rows if r["start"]),
        "namespace_only": len(namespace_only),
        "namespace_only_top60k": len(top60k(namespace_only)),
        "namespace_only_downloads": dl(namespace_only),
        "namespace_top": [{"project": p, "downloads_30d": meta[p][0]} for p in
                          sorted(namespace_only, key=lambda p: (-meta[p][0], p))[:10]],
        "namespace_files": len(ns_files),
        "namespace_files_py2": ns_py2,
        "windows_only": len(windows_only),
        "never": len(never),
        "never_projects": never,
        "windows_only_projects": windows_only,
        "start_projects": start,
        "own_top": own_rows[:40],
        "own_all": [r["project"] for r in own_rows],
    }


def write_charts(r, out):
    from svgchart import hbar
    d = out / "pth"
    d.mkdir(parents=True, exist_ok=True)
    (d / "kinds.svg").write_text(hbar([
        ("Runs its own code", r["own"]),
        ("Namespace boilerplate only", r["namespace_only"]),
        ("Runs on Windows only", r["windows_only"]),
        ("Never runs", r["never"]),
    ], unit="projects", title="What the .pth files in PyPI packages do"))
    top = [t for t in r["own_top"] if t["downloads_30d"] > 0][:10]
    (d / "top.svg").write_text(hbar(
        [(t["project"], t["downloads_30d"] / 1e6) for t in top], fmt="{:.1f}",
        unit="million downloads in 30 days",
        title="Most downloaded packages whose .pth file runs their own code at startup"))
    (d / "card.svg").write_text(results_card(r))
    (d / "card-og.svg").write_text(results_card(r, width=1200))


def results_card(r, width=560):
    from svgchart import card
    n = lambda v: f"{v:,}"
    return card([
        ("Packages that ship a .pth file with an import line", [
            (n(r["listed_projects"]), f"of {n(r['projects_all'])} indexed projects", ""),
            (n(r["running"]), "run it on every Python start after a normal install", "")]),
        ("What runs at startup", [
            (n(r["own"]), "packages run their own code", ""),
            (n(r["namespace_only"]), "only old setuptools namespace boilerplate", "")]),
        ("Ready for Python 3.15's .start files (PEP 829)", [
            (n(r["own_start"]), f"of the {n(r['own'])} that run their own code", "")]),
    ], width=width, title="PyPI packages that run code every time Python starts",
        sub="Data as of 13 Nov 2026",
        note=("Three PyPI attacks in 2026 used a .pth file: litellm 1.82.8 in March, litellm 1.107.0 in "
              "October and agent-framework 1.26.1 and 1.26.2 in November. Installing the package was "
              "enough to run the credential stealer."),
        foot=(f"Latest release of {n(r['projects_all'])} PyPI projects; each listed .pth file "
              f"downloaded and read. py-code.org"))


def main(argv):
    import duckdb
    here = Path(__file__).resolve().parent
    parquet = (argv[1] if len(argv) > 1 else HF_SNAPSHOT).rstrip("/")
    checks_path = Path(argv[2] if len(argv) > 2 else here / "results/checks.jsonl")
    out = Path(argv[3] if len(argv) > 3 else "out")
    checks = {}
    for line in open(checks_path):
        c = json.loads(line)
        checks[c["project"]] = c
    con = duckdb.connect()
    con.execute(f"CREATE VIEW p AS SELECT * FROM read_parquet('{parquet}/projects.parquet')")
    con.execute(f"CREATE VIEW t AS SELECT * FROM read_parquet('{parquet}/pth_files.parquet')")
    result = analyse(con, checks)
    out.mkdir(parents=True, exist_ok=True)
    (out / "pth.json").write_text(json.dumps(result, indent=2) + "\n")
    write_charts(result, out)
    print(json.dumps({k: v for k, v in result.items() if not isinstance(v, list)}, indent=2))


if __name__ == "__main__":
    main(sys.argv)
