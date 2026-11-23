"""Numbers for the post on PyPI code that still imports pkg_resources.

setuptools 82.0.0 (8 February 2026) removed pkg_resources. This script reads projects.parquet
and refs.parquet from the py-code.org dataset, plus checks.jsonl (written by pkg_check.py,
which reads each project's release file again and records whether each import is guarded).
It writes pkg.json, unguarded.csv (every project whose own code would fail) and the chart SVGs.

Usage: pkg_data.py [<parquet-dir>] [<checks.jsonl>] [<out-dir>]

With no arguments it reads the 13 November 2026 snapshot from Hugging Face (pinned
revision), results/checks.jsonl, and writes to ./out.
"""
import csv
import json
import sys
from pathlib import Path

from packaging.requirements import InvalidRequirement, Requirement

from pkg_check import file_kind

SNAPSHOT = "2026-11-13"
HF_SNAPSHOT = "hf://datasets/pypi-data/py-code@9d81d70d6519d77f4dee4811b3e3a5d88379c17d"
REMOVED_ON = "2026-02-08"      # setuptools 82.0.0 upload date on PyPI
ACTIVE_SINCE = "2026-05-13"    # a release in the six months before the snapshot
STALE_BEFORE = "2024-11-13"    # no release in the two years before the snapshot
SAFE = {"guarded", "fallback", "gated", "loaded"}

# pkg_resources name -> replacement, from the importlib.metadata, importlib.resources and
# packaging docs. Names not listed here get no replacement in the table.
REPLACEMENTS = {
    "get_distribution": "importlib.metadata.version(name), or distribution(name)",
    "DistributionNotFound": "importlib.metadata.PackageNotFoundError",
    "resource_filename": "importlib.resources.files(package) / path, with as_file() for a real path",
    "resource_string": "importlib.resources.files(package).joinpath(path).read_bytes()",
    "resource_stream": "importlib.resources.files(package).joinpath(path).open('rb')",
    "resource_exists": "importlib.resources.files(package).joinpath(path).is_file()",
    "resource_listdir": "importlib.resources.files(package).joinpath(path).iterdir()",
    "resource_isdir": "importlib.resources.files(package).joinpath(path).is_dir()",
    "iter_entry_points": "importlib.metadata.entry_points(group=...)",
    "load_entry_point": "importlib.metadata.entry_points(group=..., name=...), then .load()",
    "get_entry_map": "importlib.metadata.entry_points()",
    "EntryPoint": "importlib.metadata.EntryPoint",
    "working_set": "importlib.metadata.distributions()",
    "parse_version": "packaging.version.Version",
    "Requirement": "packaging.requirements.Requirement",
    "declare_namespace": "a native namespace package (PEP 420): no __init__.py",
    "require": "importlib.metadata.version() with packaging.specifiers.SpecifierSet",
}
VENDOR_DIRS = ("/_vendor/", "/vendor/", "/vendored/", "/_vendored/", "/_vendored_packages/",
               "/inline_copy/", "/node_modules/",
               "/third_party/", "/thirdparty/", "/extern/", "/_extern/", "/externals/")
REPO_HOSTS = ("github.com/", "gitlab.com/", "codeberg.org/", "bitbucket.org/", "sr.ht/")


def keeps_pkg_resources(requires_dist):
    """True when a required (non-extra) dependency still provides pkg_resources:
    setuptools pinned below 82, or the pkg-resources-backport snapshot."""
    for r in requires_dist:
        try:
            req = Requirement(r)
        except InvalidRequirement:
            continue
        if req.marker and "extra" in str(req.marker):
            continue
        name = req.name.lower().replace("_", "-")
        if name == "pkg-resources-backport":
            return True
        if name == "setuptools" and req.specifier and not req.specifier.contains("82.0.0", prereleases=True):
            return True
    return False


def repo_url(urls):
    for key in ("Source", "Source Code", "Repository", "Code", "GitHub", "Homepage", "Home-page"):
        for k, v in urls.items():
            if k.lower() == key.lower() and v and any(h in v for h in REPO_HOSTS):
                return v.rstrip("/")
    for v in urls.values():
        if v and any(h in v for h in REPO_HOSTS):
            return v.rstrip("/")
    return ""


def vendored(path):
    return any(d in "/" + path.lower() for d in VENDOR_DIRS)


def classify(check):
    """Worst context of a pkg_resources import in the project's own code files.

    module:   at module level, unguarded: the file fails to import without pkg_resources
    function: inside a function, unguarded: fails when that code runs
    pinned:   unguarded, but the project requires setuptools below 82 or pkg-resources-backport
    vendored: unguarded only in a bundled copy of another library (e.g. _vendor/, inline_copy/)
    safe:     every import is guarded, a fallback in `except`, behind a version check, or
              only runs when pkg_resources is already loaded
    setup:    only in setup.py or other build scripts
    other:    only in tests or docs, or not found again
    """
    # File kinds are recomputed from the path, so rule changes apply without a new download.
    hits = [dict(h, kind=file_kind(h["path"])) for h in check.get("hits", [])]
    code = [h for h in hits if h["kind"] == "code" and not vendored(h["path"])]
    vend = [h for h in hits if h["kind"] == "code" and vendored(h["path"])]
    ctx = {h["context"] for h in code}
    if "module" in ctx:
        level = "module"
    elif "function" in ctx:
        level = "function"
    elif any(h["context"] in ("module", "function") for h in vend):
        level = "vendored"
    elif code or vend:
        level = "safe"
    elif any(h["kind"] == "setup" for h in hits):
        level = "setup"
    else:
        level = "other"
    bad = [h for h in code if h["context"] == level] if level in ("module", "function") else []
    if bad and keeps_pkg_resources(check.get("requires_dist", [])):
        level = "pinned"
    return level, bad


def analyse(con, checks):
    projects_all = con.sql("SELECT count(*) FROM p").fetchall()[0][0]
    meta = {r[0]: r[1:] for r in con.sql(
        "SELECT project, downloads_30d, CAST(upload_time AS DATE)::VARCHAR FROM p").fetchall()}
    users = {r[0] for r in con.sql(
        "SELECT DISTINCT project FROM r WHERE name = 'pkg_resources'").fetchall()} - {"setuptools"}
    names = {}
    for project, name in con.sql(
            "SELECT DISTINCT project, name FROM r WHERE name LIKE 'pkg\\_resources.%' ESCAPE '\\' "
            "AND length(name) - length(replace(name, '.', '')) = 1").fetchall():
        names.setdefault(name.split(".", 1)[1], set()).add(project)

    levels, rows, errors = {}, [], 0
    for project in users:
        c = checks.get(project)
        if c is None or "error" in c:
            errors += 1
            level, bad = "other", []
        else:
            level, bad = classify(c)
        levels[project] = level
        if level in ("module", "function"):
            d, up = meta[project]
            rows.append({
                "project": project, "downloads_30d": d, "last_release": up, "level": level,
                "after_removal": up >= REMOVED_ON, "active": up >= ACTIVE_SINCE,
                "dynamic_only": all(h["form"] == "dynamic" for h in bad),
                "where": [f'{h["path"]}:{h["line"]}' for h in bad],
                "repo": repo_url(c.get("urls", {})),
            })
    rows.sort(key=lambda t: (-t["downloads_30d"], t["project"].lower()))
    unguarded = {t["project"] for t in rows}
    count = lambda lv: sum(1 for v in levels.values() if v == lv)
    after = [t for t in rows if t["after_removal"]]
    top60k = [t for t in rows if t["downloads_30d"] > 0]
    calls = sorted(names, key=lambda n: (-len(names[n] & users), n))
    return {
        "snapshot": SNAPSHOT,
        "setuptools_82_released": REMOVED_ON,
        "projects_all": projects_all,
        "importers": len(users),
        "importers_after_removal": sum(1 for p in users if meta[p][1] >= REMOVED_ON),
        "importers_top60k": sum(1 for p in users if meta[p][0] > 0),
        "levels": {lv: count(lv) for lv in ("module", "function", "pinned", "vendored", "safe", "setup", "other")},
        "check_errors": errors,
        "safe_by_context": {k: sum(1 for p in users if levels[p] == "safe" and checks[p].get("hits") and
                                   {h["context"] for h in checks[p]["hits"] if h["kind"] == "code"} <= SAFE and
                                   k in {h["context"] for h in checks[p]["hits"] if h["kind"] == "code"})
                            for k in sorted(SAFE)},
        "unguarded": len(rows),
        "unguarded_after_removal": len(after),
        "unguarded_no_release_2y": sum(1 for t in rows if t["last_release"] < STALE_BEFORE),
        "unguarded_active": sum(1 for t in rows if t["active"]),
        "unguarded_with_repo": sum(1 for t in rows if t["repo"]),
        "unguarded_active_with_repo": sum(1 for t in rows if t["active"] and t["repo"]),
        "unguarded_dynamic_only": sum(1 for t in rows if t["dynamic_only"]),
        "unguarded_top60k": len(top60k),
        "unguarded_top60k_downloads": sum(t["downloads_30d"] for t in top60k),
        "unguarded_after_removal_top60k": sum(1 for t in after if t["downloads_30d"] > 0),
        "calls": [{"name": n, "importers": len(names[n] & users), "unguarded": len(names[n] & unguarded),
                   "replacement": REPLACEMENTS.get(n, "")} for n in calls[:15]],
        "top": rows[:40],
        "top_after_removal": after[:20],
        "top_before_removal": [t for t in rows if not t["after_removal"]][:20],
        "levels_1m": {p: levels[p] for p in sorted(users) if meta[p][0] >= 1_000_000},
    }, rows


def write_csv(rows, path):
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["project", "downloads_30d", "last_release", "level", "where", "repository"])
        for t in rows:
            w.writerow([t["project"], t["downloads_30d"], t["last_release"], t["level"],
                        " ".join(t["where"]), t["repo"]])


LEVEL_LABELS = [
    ("module", "Unguarded, top level"),
    ("function", "Unguarded, in function"),
    ("safe", "Safe"),
    ("pinned", "Pinned or backport"),
    ("vendored", "Bundled copy only"),
    ("setup", "Build scripts only"),
    ("other", "Tests or docs only"),
]


def write_charts(r, out):
    from svgchart import hbar
    d = out / "pkg-resources"
    d.mkdir(parents=True, exist_ok=True)
    (d / "levels.svg").write_text(hbar(
        [(label, r["levels"][lv]) for lv, label in LEVEL_LABELS], unit="projects",
        title=f"How the {r['importers']:,} projects that use pkg_resources import it"))
    calls = sorted((c for c in r["calls"] if c["unguarded"]), key=lambda c: -c["unguarded"])[:10]
    (d / "calls.svg").write_text(hbar(
        [(c["name"], c["unguarded"]) for c in calls], unit="projects",
        title="pkg_resources names used by projects with an unguarded import"))
    top = [t for t in r["top_after_removal"] if t["downloads_30d"] > 0][:10]
    if top:
        (d / "after.svg").write_text(hbar(
            [(t["project"], t["downloads_30d"] / 1e3) for t in top],
            unit="thousand downloads in 30 days", fmt="{:,.0f}",
            title="Most downloaded projects released after setuptools 82 with an unguarded pkg_resources import"))
    (d / "card.svg").write_text(results_card(r))
    (d / "card-og.svg").write_text(results_card(r, width=1200))


def results_card(r, width=560):
    from svgchart import card
    n = lambda v: f"{v:,}"
    return card([
        ("Projects that use pkg_resources", [
            (n(r["importers"]), f"of {n(r['projects_all'])} indexed projects", ""),
            (n(r["unguarded"]), "with an unguarded import in their own code", "")]),
        ("Released after setuptools 82 removed it", [
            (n(r["importers_after_removal"]), "still use pkg_resources", ""),
            (n(r["unguarded_after_removal"]), "with an unguarded import", "")]),
        ("Ready for a fix", [
            (n(r["unguarded_active_with_repo"]), "unguarded, released in the last 6 months, with a public repo", "")]),
    ], width=width, title="PyPI code that still imports pkg_resources",
        sub="Data as of 13 Nov 2026",
        note="setuptools 82.0.0 (8 Feb 2026) removed pkg_resources. An unguarded import fails "
             "with ModuleNotFoundError unless setuptools is pinned below 82.",
        foot=f"Latest release of {n(r['projects_all'])} projects. py-code.org")


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
    con.execute(f"CREATE VIEW r AS SELECT project, name FROM read_parquet('{parquet}/refs.parquet') "
                f"WHERE module = 'pkg_resources'")
    result, rows = analyse(con, checks)
    out.mkdir(parents=True, exist_ok=True)
    (out / "pkg.json").write_text(json.dumps(result, indent=2) + "\n")
    write_csv(rows, out / "unguarded.csv")
    write_charts(result, out)
    print(json.dumps({k: v for k, v in result.items() if k not in ("top", "top_after_removal", "calls")}, indent=2))


if __name__ == "__main__":
    main(sys.argv)
