"""Numbers for the "what new PyPI packages are made of" post.

Reads projects.parquet and refs.parquet from the py-code.org dataset and writes
new-packages.json plus the chart SVGs.

Usage: blog_data.py [<parquet-dir>] [<out-dir>]

With no arguments it reads the 13 November 2026 snapshot from Hugging Face
(pinned revision, so the numbers match the post) and writes to ./out.
"""
import json
import sys
from pathlib import Path

SNAPSHOT = "2026-11-13"
HF_SNAPSHOT = "hf://datasets/pypi-data/py-code@9d81d70d6519d77f4dee4811b3e3a5d88379c17d"
RECENT_FROM = "2025-11-13"

# SDK name -> predicate on refs (r.module, or r.name for google.genai, whose
# module is just "google"). langchain* is any module starting with langchain.
SDKS = {
    "openai": "openai",
    "anthropic": "anthropic",
    "litellm": "litellm",
    "langchain": "langchain*",
    "google-genai": "google.genai",
    "ollama": "ollama",
    "mcp": "mcp",
}
LLM_SDKS = [k for k in SDKS if k != "mcp"]
HTTP_LIBS = ["requests", "httpx", "aiohttp"]

# Own packages: a project whose normalised name is the library's name, or starts
# with it followed by "-" (langchain-openai, mcp-server-git, requests-toolbelt),
# is not counted for that library, so each count shows projects built on top of
# it. The same rule as the AI tools posts.
# Copies: the iflow-mcp* projects republish other people's MCP servers under one
# prefix, and are left out of every count. Totals (projects_all, projects_recent)
# still include them.
COPY_FAMILIES = ["iflow-mcp"]


def _norm_sql(col):
    return f"replace(replace(lower({col}), '_', '-'), '.', '-')"


def _keep(col, family):
    """SQL condition: the project is neither one of `family`'s own packages nor a copy."""
    n = _norm_sql(col)
    copies = " OR ".join(f"starts_with(lower({col}), '{c}')" for c in COPY_FAMILIES)
    return f"NOT ({n} = '{family}' OR starts_with({n}, '{family}-') OR {copies})"


def _predicate(match):
    if match.endswith("*"):
        return f"r.module LIKE '{match[:-1]}%'"
    if "." in match:
        return f"(r.name = '{match}' OR r.name LIKE '{match}.%')"
    return f"r.module = '{match}'"


# One row per (project, sdk): a project is counted once per SDK, however many
# of its modules match. Refs are filtered before any join.
SQL_SDK_USE = " UNION ALL ".join(
    f"SELECT DISTINCT r.project, '{sdk}' AS sdk FROM r WHERE {_predicate(m)} AND {_keep('r.project', sdk)}"
    for sdk, m in SDKS.items()
)

SQL_COUNT_RECENT = f"SELECT count(*) FROM p WHERE upload_time >= '{RECENT_FROM}'"

SQL_SDKS = f"""
WITH use AS ({SQL_SDK_USE})
SELECT s.sdk, count(DISTINCT p.project) AS projects
FROM (SELECT unnest([{", ".join(repr(k) for k in SDKS)}]) AS sdk) s
LEFT JOIN use u ON u.sdk = s.sdk
LEFT JOIN p ON p.project = u.project AND p.upload_time >= '{RECENT_FROM}'
GROUP BY s.sdk
"""

# Projects whose latest release is in each month, and how many of them use any
# LLM SDK or MCP.
SQL_MONTHS = f"""
WITH use AS ({SQL_SDK_USE}),
llm AS (SELECT DISTINCT project FROM use WHERE sdk IN ({", ".join(repr(k) for k in LLM_SDKS)})),
mcp AS (SELECT DISTINCT project FROM use WHERE sdk = 'mcp')
SELECT strftime(p.upload_time, '%Y-%m') AS month,
       count(*) AS projects,
       count(llm.project) AS llm,
       count(mcp.project) AS mcp
FROM p
LEFT JOIN llm ON llm.project = p.project
LEFT JOIN mcp ON mcp.project = p.project
WHERE p.upload_time >= '{RECENT_FROM}'
GROUP BY month ORDER BY month
"""

# Projects using each HTTP library, with their share of the 30-day downloads of
# all projects that use at least one of the three.
SQL_HTTP_USE = " UNION ALL ".join(
    f"SELECT DISTINCT project, module AS lib FROM r WHERE module = '{lib}' AND {_keep('project', lib)}"
    for lib in HTTP_LIBS
)

SQL_HTTP = f"""
WITH use AS ({SQL_HTTP_USE}),
dl AS (SELECT u.lib, u.project, coalesce(p.downloads_30d, 0) AS d
       FROM use u JOIN p ON p.project = u.project),
grp AS (SELECT sum(d) AS total, count(*) AS n
        FROM (SELECT project, max(d) AS d FROM dl GROUP BY project))
SELECT lib, count(*) AS projects, sum(d) AS downloads,
       sum(d) / nullif(any_value(grp.total), 0) AS download_share,
       count(*) * 1.0 / any_value(grp.n) AS project_share
FROM dl, grp GROUP BY lib ORDER BY lib
"""

# pydantic v1 validators vs v2 validators, among projects using pydantic.
# `pydantic.v1` (the compatibility namespace) is its own flag: it is not
# counted as v1 or v2 use. v1_only/v2_only/both are exclusive groups.
SQL_PYDANTIC_FLAGS = f"""
SELECT project,
       bool_or(name IN ('pydantic.validator', 'pydantic.root_validator')) AS v1,
       bool_or(name IN ('pydantic.field_validator', 'pydantic.model_validator')) AS v2,
       bool_or(name = 'pydantic.v1' OR name LIKE 'pydantic.v1.%') AS shim
FROM r WHERE module = 'pydantic' AND {_keep('project', 'pydantic')} GROUP BY project
"""

SQL_PYDANTIC = f"""
WITH f AS ({SQL_PYDANTIC_FLAGS}),
j AS (SELECT f.*, coalesce(p.downloads_30d, 0) AS d
      FROM f JOIN p ON p.project = f.project)
SELECT count(*) AS users, coalesce(sum(d), 0) AS d_all,
       count(*) FILTER (v1 AND NOT v2) AS v1_only,
       count(*) FILTER (v2 AND NOT v1) AS v2_only,
       count(*) FILTER (v1 AND v2) AS both,
       count(*) FILTER (shim) AS shim,
       coalesce(sum(d) FILTER (v1 AND NOT v2), 0) AS d_v1,
       coalesce(sum(d) FILTER (v2 AND NOT v1), 0) AS d_v2
FROM j
"""

SQL_PYDANTIC_TOP_V1 = f"""
WITH f AS ({SQL_PYDANTIC_FLAGS})
SELECT f.project, coalesce(p.downloads_30d, 0) AS d
FROM f JOIN p ON p.project = f.project
WHERE f.v1 AND NOT f.v2
ORDER BY d DESC, f.project LIMIT 10
"""

# Recent projects using parts of the MCP SDK: servers vs clients.
MCP_NAMES = ["mcp.server", "mcp.server.fastmcp.FastMCP", "mcp.ClientSession"]
SQL_MCP_NAMES = f"""
SELECT r.name, count(DISTINCT r.project)
FROM r JOIN p ON p.project = r.project AND p.upload_time >= '{RECENT_FROM}'
WHERE r.name IN ({", ".join(repr(n) for n in MCP_NAMES)}) AND {_keep('r.project', 'mcp')}
GROUP BY r.name
"""

# Recent projects using the MCP client API, counted once (mcp.client covers
# mcp.client.stdio etc.; the index records every prefix of a dotted name).
MCP_CLIENT_NAMES = ["mcp.client", "mcp.ClientSession"]
SQL_MCP_CLIENT = f"""
SELECT count(DISTINCT r.project)
FROM r JOIN p ON p.project = r.project AND p.upload_time >= '{RECENT_FROM}'
WHERE r.name IN ({", ".join(repr(n) for n in MCP_CLIENT_NAMES)}) AND {_keep('r.project', 'mcp')}
"""

SQL_HTTP_GROUP = f"""
SELECT count(*), coalesce(sum(coalesce(p.downloads_30d, 0)), 0)
FROM p WHERE p.project IN (SELECT project FROM ({SQL_HTTP_USE}))
"""

# How many projects the own-package and copy rules leave out, per library.
# SDKs are counted among recent projects, as in the post; the rest among all.
def _dropped_sql(lib, match, recent):
    n = _norm_sql("r.project")
    own = f"({n} = '{lib}' OR starts_with({n}, '{lib}-'))"
    copies = " OR ".join(f"starts_with(lower(r.project), '{c}')" for c in COPY_FAMILIES)
    join = f"JOIN p ON p.project = r.project AND p.upload_time >= '{RECENT_FROM}'" if recent else ""
    return (f"SELECT count(DISTINCT r.project) FILTER (WHERE {own}), "
            f"count(DISTINCT r.project) FILTER (WHERE NOT {own} AND ({copies})) "
            f"FROM r {join} WHERE {match}")

DEFINITIONS = {
    "download_share": (
        "Sum of downloads_30d over the projects using the library, divided by the "
        "sum of downloads_30d over the projects using any library in the same "
        "comparison group. A project using several libraries counts in each. For "
        "http the group is requests, httpx and aiohttp; for pydantic it is every "
        "project using pydantic."
    ),
    "project_share": "Projects using the library divided by projects in the group.",
    "http_group": "Denominator for the http shares: projects using any of requests, httpx or aiohttp (http_group.projects) and their summed downloads_30d (http_group.downloads).",
    "pydantic_group": "Denominator for the pydantic shares: projects using pydantic (pydantic.users) and their summed downloads_30d (pydantic.downloads).",
    "projects_all": "Every indexed project; the http and pydantic numbers use all of them.",
    "llm_any": "Recent projects using any LLM SDK (MCP not counted), each counted once.",
    "mcp_names": "Recent projects whose code uses each of these MCP SDK names.",
    "mcp_client": "Recent projects using the MCP client API (mcp.client or mcp.ClientSession), each counted once.",
    "own_dropped": "Projects left out of each library's count because they are its own packages (own) or iflow-mcp copies (copies). SDKs: recent projects; requests, httpx, aiohttp, pydantic: all projects.",
    "own_packages": "A project whose normalised name equals the library's name or starts with it followed by '-' is not counted for that library. iflow-mcp* copies are not counted for any library.",
    "recent": f"Latest release uploaded on or after {RECENT_FROM}.",
    "llm_sdks": "Projects using any of: " + ", ".join(LLM_SDKS) + ", counted once.",
    "langchain": "Any module starting with 'langchain'.",
    "google-genai": "Refs named google.genai or google.genai.* (module is 'google').",
    "pydantic_v1": "v1-only: uses pydantic.validator or pydantic.root_validator and no v2 validator.",
    "pydantic_v2": "v2-only: uses pydantic.field_validator or pydantic.model_validator and no v1 validator.",
    "pydantic_both": "Uses both a v1 and a v2 validator.",
    "pydantic_v1_namespace": "Uses pydantic.v1 (compatibility namespace). Counted separately; it is not v1 or v2 use.",
    "pydantic_top_v1": "Top 10 v1-only projects by downloads_30d; check them, since compat shims inflate v1.",
}


def _share(a, b):
    return a / b if b else 0.0


def analyse(con):
    projects_recent = con.execute(SQL_COUNT_RECENT).fetchone()[0]
    projects_all = con.execute("SELECT count(*) FROM p").fetchone()[0]
    month_rows = con.execute(SQL_MONTHS).fetchall()
    sdk_rows = {s: n for s, n in con.execute(SQL_SDKS).fetchall()}
    sdks = [[s, sdk_rows.get(s, 0)] for s in SDKS]
    http_rows = con.execute(SQL_HTTP).fetchall()
    http = {l: (n, ds, ps) for l, n, _, ds, ps in http_rows}
    http_group = con.execute(SQL_HTTP_GROUP).fetchone()
    (users, d_all, v1, v2, both, shim, d_v1, d_v2) = con.execute(SQL_PYDANTIC).fetchone()
    top_v1 = con.execute(SQL_PYDANTIC_TOP_V1).fetchall()
    mcp_names = dict(con.execute(SQL_MCP_NAMES).fetchall())
    mcp_client = con.execute(SQL_MCP_CLIENT).fetchone()[0]
    libs = HTTP_LIBS
    dropped = {}
    for lib, match in SDKS.items():
        own, cp = con.execute(_dropped_sql(lib, _predicate(match), True)).fetchone()
        dropped[lib] = {"own": own, "copies": cp}
    for lib in HTTP_LIBS + ["pydantic"]:
        own, cp = con.execute(_dropped_sql(lib, f"r.module = '{lib}'", False)).fetchone()
        dropped[lib] = {"own": own, "copies": cp}
    return {
        "snapshot": SNAPSHOT,
        "projects_recent": projects_recent,
        "projects_all": projects_all,
        "llm_any": sum(l for _, _, l, _ in month_rows),
        "definitions": DEFINITIONS,
        "own_dropped": dropped,
        "months": [[m, n, _share(l, n), _share(c, n)] for m, n, l, c in month_rows],
        "month_counts": [[m, l, c] for m, n, l, c in month_rows],
        "sdks": sdks,
        "mcp_names": [[n, mcp_names.get(n, 0)] for n in MCP_NAMES],
        "mcp_client": mcp_client,
        "sdks_share": [[s, _share(n, projects_recent)] for s, n in sdks],
        "http": [[l, http.get(l, (0, 0, 0))[0], float(http.get(l, (0, 0, 0))[1] or 0)]
                 for l in libs],
        "http_project_share": {l: float(http.get(l, (0, 0, 0))[2] or 0) for l in libs},
        "http_group": {"projects": http_group[0], "downloads": int(http_group[1])},
        "pydantic": {
            "v1": [v1, _share(d_v1, d_all)],
            "v2": [v2, _share(d_v2, d_all)],
            "both": both,
            "v1_namespace": shim,
            "users": users,
            "downloads": int(d_all),
            "project_share": {"v1": _share(v1, users), "v2": _share(v2, users)},
            "top_v1": [[n, int(d)] for n, d in top_v1],
        },
    }


MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
SDK_LABELS = {"mcp": "mcp (MCP SDK)"}


def write_charts(result, out):
    """Write blog-data/new-packages/{months,sdks,http,pydantic}.svg."""
    from svgchart import columns, hbar

    d = out / "new-packages"
    d.mkdir(parents=True, exist_ok=True)
    partial = result["snapshot"][:7]
    months = []
    for m, _, llm_share, _ in result["months"]:
        y, mo = m.split("-")
        star = "*" if m == partial else ""
        months.append((f"{MONTH_NAMES[int(mo) - 1]} {y[2:]}{star}", llm_share * 100))
    (d / "months.svg").write_text(columns(
        months, fmt="{:.1f}", unit="% of projects (* month so far)",
        title="Recent projects importing an LLM SDK, counted by the month of their latest release"))
    sdks = sorted(result["sdks"], key=lambda r: -r[1])
    (d / "sdks.svg").write_text(hbar(
        [(SDK_LABELS.get(s, s), n) for s, n in sdks], unit="projects",
        title="Recent projects using each SDK"))
    http = sorted(result["http"], key=lambda r: -r[1])
    (d / "http.svg").write_text(hbar(
        [(l, n) for l, n, _ in http], unit="projects",
        title="Projects using each HTTP library"))
    py = result["pydantic"]
    (d / "pydantic.svg").write_text(hbar(
        [("v2 validators only", py["v2"][0]), ("both", py["both"]),
         ("v1 validators only", py["v1"][0]), ("imports pydantic.v1", py["v1_namespace"])],
        unit="projects", title="Pydantic projects by validator API"))
    (d / "card.svg").write_text(results_card(result))
    (d / "card-og.svg").write_text(results_card(result, width=1200))


def _day(iso):
    y, m, d = iso.split("-")
    return f"{int(d)} {MONTH_NAMES[int(m) - 1]} {y}"


def results_card(r, width=560):
    """The card under the post's H1: four findings, one note, both scopes."""
    n = lambda v: f"{v:,}"
    sdks, http, py = dict(r["sdks"]), {l: c for l, c, _ in r["http"]}, r["pydantic"]
    peak_m, _, peak, _ = max(r["months"], key=lambda m: m[2])
    y, mo = peak_m.split("-")
    fewer = (1 - http["httpx"] / http["requests"]) * 100
    from svgchart import card
    return card([
        ("Most imported AI SDK, recent projects", [
            (n(sdks["mcp"]), "import mcp, the MCP SDK", "win"),
            (n(sdks["openai"]), "import openai", "")]),
        ("LLM SDK share, best month, recent projects", [
            (f"{peak * 100:.1f}%", f"of projects whose latest release came out in "
                                   f"{MONTH_NAMES[int(mo) - 1]} {y}; MCP not counted", "")]),
        ("HTTP client, all indexed projects", [
            (n(http["requests"]), "import requests", ""),
            (n(http["httpx"]), f"import httpx, {fewer:.0f}% fewer", "")]),
        ("pydantic validators, all indexed projects", [
            (n(py["v2"][0]), "use only v2 validators", "win"),
            (n(py["v1"][0]), "use only v1 validators", "")]),
    ], width=width, title="What new PyPI packages import", sub=f"Data as of {_day(r['snapshot'])}",
        note=(f"Surprise: the MCP SDK alone is in {n(sdks['mcp'])} recent projects, against "
              f"{n(r['llm_any'])} that use any of the six LLM SDKs, each counted once."),
        foot=(f"SDK rows: latest release of {n(r['projects_recent'])} projects released "
              f"{_day(RECENT_FROM)} \u2013 {_day(r['snapshot'])}. HTTP and pydantic rows: all "
              f"{n(r['projects_all'])} indexed projects. Each library's own packages are not "
              f"counted. py-code.org"))


def main(argv):
    import duckdb

    parquet = (argv[1] if len(argv) > 1 else HF_SNAPSHOT).rstrip("/")
    out = Path(argv[2] if len(argv) > 2 else "out")
    con = duckdb.connect()
    con.execute(f"CREATE VIEW p AS SELECT * FROM read_parquet('{parquet}/projects.parquet')")
    con.execute(f"CREATE VIEW r AS SELECT * FROM read_parquet('{parquet}/refs.parquet')")
    result = analyse(con)
    out.mkdir(parents=True, exist_ok=True)
    (out / "new-packages.json").write_text(json.dumps(result, indent=2) + "\n")
    write_charts(result, out)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main(sys.argv)
