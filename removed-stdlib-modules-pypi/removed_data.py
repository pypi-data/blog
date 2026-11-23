"""Numbers for the post on PyPI code that imports modules removed in Python 3.12 and 3.13.

Reads projects.parquet and refs.parquet from the py-code.org dataset, plus checks.jsonl
(written by removed_check.py, which reads each project's release file again and records
whether each import is guarded). Writes removed.json and the chart SVGs.

Usage: removed_data.py [<parquet-dir>] [<checks.jsonl>] [<out-dir>]

With no arguments it reads the current dataset from Hugging Face (rebuilt weekly, so the
numbers drift from the post's), results/checks.jsonl, and writes to ./out.
"""
import json
import sys
from pathlib import Path

SNAPSHOT = "2026-11-13"
HF_SNAPSHOT = "hf://datasets/pypi-data/py-code"
STALE_BEFORE = "2024-11-13"   # no release in the two years before the snapshot

# module -> (removed in, replacement named in the "What's New" page or a PyPI backport)
MODULES = {
    "distutils": ("3.12", "setuptools (still ships distutils), or sysconfig, shutil.which, packaging"),
    "imp": ("3.12", "importlib; zombie-imp on PyPI"),
    "asyncore": ("3.12", "asyncio; pyasyncore on PyPI"),
    "asynchat": ("3.12", "asyncio; pyasynchat on PyPI"),
    "smtpd": ("3.12", "aiosmtpd on PyPI"),
    "cgi": ("3.13", "urllib.parse, email.message; legacy-cgi on PyPI"),
    "cgitb": ("3.13", "legacy-cgi on PyPI"),
    "audioop": ("3.13", "audioop-lts on PyPI"),
    "pipes": ("3.13", "subprocess, shlex.quote"),
    "imghdr": ("3.13", "filetype, puremagic; standard-imghdr on PyPI"),
    "telnetlib": ("3.13", "telnetlib3, Exscript; standard-telnetlib on PyPI"),
    "crypt": ("3.13", "hashlib, bcrypt, argon2-cffi; crypt_r on PyPI"),
    "lib2to3": ("3.13", "none in the standard library"),
    "xdrlib": ("3.13", "standard-xdrlib on PyPI"),
    "uu": ("3.13", "base64"),
    "sndhdr": ("3.13", "filetype, puremagic; standard-sndhdr on PyPI"),
    "aifc": ("3.13", "standard-aifc on PyPI"),
    "sunau": ("3.13", "standard-sunau on PyPI"),
    "chunk": ("3.13", "standard-chunk on PyPI"),
    "mailcap": ("3.13", "mimetypes"),
    "nntplib": ("3.13", "pynntp; standard-nntplib on PyPI"),
    "msilib": ("3.13", "none"),
    "nis": ("3.13", "none"),
    "spwd": ("3.13", "python-pam"),
    "ossaudiodev": ("3.13", "pygame"),
}
# Packages the post names; their downloads and last release go into removed.json.
EXAMPLES = ["nose", "boto", "pydub", "coreapi", "htmlmin", "PGPy", "coloredlogs", "humanfriendly",
            "docker-pycreds", "aioredis", "arsenic", "python-editor", "GPUtil", "pip"]
# Projects that provide the module themselves: setuptools ships distutils.
PROVIDERS = {"setuptools": {"distutils"}}
BACKPORT_MODULES = {"legacy-cgi": ("cgi", "cgitb"), "audioop-lts": ("audioop",), "zombie-imp": ("imp",),
                    "pyasyncore": ("asyncore",), "pyasynchat": ("asynchat",), "crypt-r": ("crypt",),
                    "setuptools": ("distutils",)}


def _covered(requires_dist):
    """Removed modules a project gets back through a required (non-extra) dependency."""
    covered = set()
    for r in requires_dist:
        req, _, marker = r.partition(";")
        if "extra" in marker:
            continue
        name = req.strip().lower().replace("_", "-")
        for sep in "<>=!~[ (":
            name = name.split(sep)[0]
        if name.startswith("standard-"):
            covered.add(name[len("standard-"):])
        covered |= set(BACKPORT_MODULES.get(name, ()))
    return covered


def classify(check):
    """Worst context of a removed import in the project's own code files.

    module:   at module level, unguarded: the file fails to import on the new Python
    function: inside a function, unguarded: fails when that code runs
    safe:     every import is guarded, a fallback in `except`, or behind a version check
    other:    only in tests, setup scripts or docs, or not found again
    """
    provided = PROVIDERS.get(check["project"], set()) | _covered(check.get("requires_dist", []))
    hits = [h for h in check.get("hits", []) if h["module"] not in provided]
    code = [h for h in hits if h["kind"] == "code"]
    ctx = {h["context"] for h in code}
    if "module" in ctx:
        level = "module"
    elif "function" in ctx:
        level = "function"
    elif code:
        level = "safe"
    else:
        level = "other"
    bad = [h for h in code if h["context"] == level] if level in ("module", "function") else []
    return level, bad


def analyse(con, checks):
    mods = list(MODULES)
    inl = ",".join(f"'{m}'" for m in mods)
    projects_all = con.sql("SELECT count(*) FROM p").fetchall()[0][0]
    meta = {r[0]: r[1:] for r in con.sql(
        "SELECT project, downloads_30d, CAST(upload_time AS DATE)::VARCHAR, requires_python FROM p").fetchall()}
    users = {}
    for project, module in con.sql(
            f"SELECT DISTINCT project, module FROM r WHERE name = module AND module IN ({inl})").fetchall():
        users.setdefault(project, set()).add(module)
    for prov, ms in PROVIDERS.items():
        if prov in users:
            users[prov] -= ms
            if not users[prov]:
                del users[prov]

    levels, per_module = {}, {m: {"index": 0, "top_level": 0, "function": 0, "safe": 0, "other": 0} for m in mods}
    top = []
    errors = 0
    for project, ms in users.items():
        c = checks.get(project)
        if c is None or "error" in c:
            errors += 1
            level, bad = "other", []
        else:
            level, bad = classify(c)
        levels[project] = level
        for m in ms:
            per_module[m]["index"] += 1
        if c and "hits" in c:
            provided = PROVIDERS.get(project, set()) | _covered(c.get("requires_dist", []))
            for m in {h["module"] for h in c["hits"] if h["module"] not in provided}:
                code = [h for h in c["hits"] if h["module"] == m and h["kind"] == "code"]
                ctx = {h["context"] for h in code}
                lv = ("top_level" if "module" in ctx else "function" if "function" in ctx
                      else "safe" if code else "other")
                per_module[m][lv] += 1
        if level in ("module", "function"):
            d, up, rp = meta[project]
            top.append({
                "project": project, "downloads_30d": d, "last_release": up,
                "requires_python": rp or "", "level": level,
                "modules": sorted({h["module"] for h in bad}),
                "where": [f'{h["path"]}:{h["line"]}' for h in bad[:3]],
                "stale": up < STALE_BEFORE,

            })
    top.sort(key=lambda t: -t["downloads_30d"])
    count = lambda lv: sum(1 for v in levels.values() if v == lv)
    broken = [t for t in top]
    in_top = [t for t in broken if t["downloads_30d"] > 0]
    stale = [t for t in in_top if t["stale"]]
    only_distutils = [t for t in broken if t["modules"] == ["distutils"]]
    return {
        "snapshot": SNAPSHOT,
        "projects_all": projects_all,
        "importers": len(users),
        "importers_top60k": sum(1 for p in users if meta[p][0] > 0),
        "levels": {lv: count(lv) for lv in ("module", "function", "safe", "other")},
        "check_errors": errors,
        "unguarded": len(broken),
        "unguarded_top60k": len(in_top),
        "unguarded_top60k_downloads": sum(t["downloads_30d"] for t in in_top),
        "unguarded_only_distutils": len(only_distutils),
        "covered_by_dependency": sum(1 for p, c in checks.items() if p in users and "hits" in c
                                     and {h["module"] for h in c["hits"]} & _covered(c.get("requires_dist", []))),
        "stale_top60k": len(stale),
        "stale_top60k_downloads": sum(t["downloads_30d"] for t in stale),
        "modules": [{"module": m, "removed_in": MODULES[m][0], "replacement": MODULES[m][1], **per_module[m]}
                    for m in sorted(mods, key=lambda m: -per_module[m]["index"])],
        "examples": {e: {"downloads_30d": meta[e][0], "last_release": meta[e][1],
                         "level": levels.get(e)} for e in EXAMPLES},
        "top": broken[:40],
        "top_stale": stale[:20],
    }


def write_charts(r, out):
    from svgchart import hbar
    d = out / "removed-modules"
    d.mkdir(parents=True, exist_ok=True)
    mods = sorted(r["modules"], key=lambda m: -(m["top_level"] + m["function"]))[:10]
    (d / "modules.svg").write_text(hbar(
        [(m["module"], m["top_level"] + m["function"]) for m in mods], unit="projects",
        title="Projects with an unguarded import of each removed module"))
    stale = r["top_stale"][:10]
    (d / "stale.svg").write_text(hbar(
        [(f'{t["project"]} ({t["last_release"][:4]})', t["downloads_30d"] / 1e6) for t in stale],
        unit="million downloads in 30 days (year of last release)", fmt="{:.1f}",
        title="Most downloaded projects with no release since November 2024 and an unguarded removed import"))
    (d / "card.svg").write_text(results_card(r))
    (d / "card-og.svg").write_text(results_card(r, width=1200))


def results_card(r, width=560):
    from svgchart import card
    n = lambda v: f"{v:,}"
    lv = r["levels"]
    top = r["top_stale"][0] if r["top_stale"] else None
    return card([
        ("Projects that import a removed module", [
            (n(r["importers"]), f"of {n(r['projects_all'])} indexed projects", ""),
            (n(r["unguarded"]), "with an unguarded import in their own code", "")]),
        ("Of the 60,000 most downloaded", [
            (n(r["unguarded_top60k"]), "with an unguarded import", ""),
            (n(r["stale_top60k"]), "of them with no release in two years", "")]),
        ("Downloads of those stale projects", [
            (f'{r["stale_top60k_downloads"] / 1e6:,.0f}M', "in the 30 days before the scan", "")]),
    ], width=width, title="PyPI code that breaks on Python 3.12 and 3.13",
        sub="Data as of 13 Nov 2026",
        note=(f"import nose and import boto fail on Python 3.12 and later, yet the two still get "
              f"{(r['examples']['nose']['downloads_30d'] + r['examples']['boto']['downloads_30d']) / 1e6:.1f}M "
              f"downloads a month. Their last releases: {r['examples']['nose']['last_release'][:4]} and "
              f"{r['examples']['boto']['last_release'][:4]}."),
        foot=(f"Removed in 3.12: distutils, imp, asyncore, asynchat, smtpd. In 3.13: the 19 PEP 594 "
              f"modules and lib2to3. Latest release of {n(r['projects_all'])} projects. py-code.org"))


def main(argv):
    import duckdb
    here = Path(__file__).resolve().parent
    parquet = (argv[1] if len(argv) > 1 else HF_SNAPSHOT).rstrip("/")
    checks_path = Path(argv[2] if len(argv) > 2 else here / "results" / "checks.jsonl")
    out = Path(argv[3] if len(argv) > 3 else "out")
    checks = {}
    for line in open(checks_path):
        c = json.loads(line)
        checks[c["project"]] = c
    con = duckdb.connect()
    con.execute(f"CREATE VIEW p AS SELECT * FROM read_parquet('{parquet}/projects.parquet')")
    con.execute(f"CREATE VIEW r AS SELECT project, name, module FROM read_parquet('{parquet}/refs.parquet')")
    result = analyse(con, checks)
    out.mkdir(parents=True, exist_ok=True)
    (out / "removed.json").write_text(json.dumps(result, indent=2) + "\n")
    write_charts(result, out)
    print(json.dumps({k: v for k, v in result.items() if k not in ("top", "top_stale", "modules")}, indent=2))


if __name__ == "__main__":
    main(sys.argv)
