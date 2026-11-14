import duckdb
import pytest

from blog_data import analyse


def build(projects, refs):
    """projects: (name, upload_time, downloads); refs: (project, name, module)."""
    con = duckdb.connect()
    con.execute("CREATE TABLE p (project VARCHAR, upload_time TIMESTAMP, downloads_30d BIGINT)")
    con.execute("CREATE TABLE r (project VARCHAR, name VARCHAR, module VARCHAR)")
    con.executemany("INSERT INTO p VALUES (?, ?, ?)", projects)
    con.executemany("INSERT INTO r VALUES (?, ?, ?)", refs)
    return con


def test_any_sdk_counts_project_once():
    con = build(
        [("a", "2026-03-05", 0), ("b", "2026-03-06", 0)],
        [("a", "openai.OpenAI", "openai"), ("a", "langchain_core.x", "langchain_core"),
         ("a", "langchain.y", "langchain"), ("b", "os.path", "os")],
    )
    out = analyse(con)
    assert out["months"] == [["2026-03", 2, 0.5, 0.0]]
    assert out["month_counts"] == [["2026-03", 1, 0]]
    assert dict(out["sdks"])["langchain"] == 1  # once, despite two langchain modules
    assert dict(out["sdks"])["openai"] == 1


def test_google_genai_matches_on_name_not_module():
    con = build(
        [("a", "2026-03-05", 0), ("b", "2026-03-05", 0)],
        [("a", "google.genai.Client", "google"), ("b", "google.auth.x", "google")],
    )
    assert dict(analyse(con)["sdks"])["google-genai"] == 1


def test_recent_filter():
    con = build(
        [("old", "2024-01-01", 10), ("new", "2026-03-05", 30)],
        [("old", "openai.OpenAI", "openai"), ("old", "requests.get", "requests"),
         ("new", "requests.get", "requests")],
    )
    out = analyse(con)
    assert out["projects_recent"] == 1
    assert [m[0] for m in out["months"]] == ["2026-03"]
    assert dict(out["sdks"])["openai"] == 0
    assert dict(((h[0], h[1]) for h in out["http"]))["requests"] == 2


def test_pydantic_split():
    con = build(
        [(n, "2026-03-05", 0) for n in "abcd"],
        [("a", "pydantic.validator", "pydantic"),
         ("b", "pydantic.field_validator", "pydantic"),
         ("c", "pydantic.validator", "pydantic"), ("c", "pydantic.field_validator", "pydantic"),
         ("d", "pydantic.BaseModel", "pydantic")],
    )
    out = analyse(con)["pydantic"]
    assert out["v1"][0] == 1 and out["v2"][0] == 1 and out["both"] == 1
    assert out["users"] == 4


def test_pydantic_v1_namespace_is_separate():
    con = build(
        [("shim", "2026-03-05", 500), ("shimonly", "2026-03-05", 100),
         ("old", "2026-03-05", 50), ("new", "2026-03-05", 50)],
        [("shim", "pydantic.v1", "pydantic"), ("shim", "pydantic.field_validator", "pydantic"),
         ("shimonly", "pydantic.v1.BaseModel", "pydantic"),
         ("old", "pydantic.validator", "pydantic"),
         ("new", "pydantic.field_validator", "pydantic")],
    )
    out = analyse(con)["pydantic"]
    assert out["v1_namespace"] == 2
    assert out["v1"][0] == 1 and out["v2"][0] == 2 and out["both"] == 0
    assert out["downloads"] == 700
    assert out["v1"][1] == pytest.approx(50 / 700)
    assert out["v2"][1] == pytest.approx(550 / 700)
    assert out["top_v1"] == [["old", 50]]


def test_download_share():
    con = build(
        [("a", "2026-03-05", 100), ("b", "2026-03-05", 300), ("c", "2026-03-05", 600)],
        [("a", "requests.get", "requests"), ("b", "httpx.get", "httpx"),
         ("b", "requests.get", "requests"), ("c", "aiohttp.x", "aiohttp"),
         ("a", "pydantic.validator", "pydantic"), ("b", "pydantic.field_validator", "pydantic")],
    )
    out = analyse(con)
    http = {h[0]: h for h in out["http"]}
    # group downloads = 1000; requests = a+b = 400; httpx = 300; aiohttp = 600
    assert http["requests"][2] == pytest.approx(0.4)
    assert http["httpx"][2] == pytest.approx(0.3)
    assert http["aiohttp"][2] == pytest.approx(0.6)
    assert out["http_project_share"]["requests"] == pytest.approx(2 / 3)
    # pydantic group = a+b = 400
    assert out["pydantic"]["v1"][1] == pytest.approx(0.25)
    assert out["pydantic"]["v2"][1] == pytest.approx(0.75)
    assert out["http_group"] == {"projects": 3, "downloads": 1000}
    assert out["pydantic"]["users"] == 2 and out["pydantic"]["downloads"] == 400
    assert "download_share" in out["definitions"]


def test_projects_all_and_llm_any():
    con = build(
        [("old", "2024-01-01", 10), ("a", "2026-03-05", 0), ("b", "2026-04-05", 0)],
        [("a", "openai.OpenAI", "openai"), ("a", "anthropic.Anthropic", "anthropic"),
         ("b", "mcp.server", "mcp"), ("old", "openai.OpenAI", "openai")],
    )
    out = analyse(con)
    assert out["projects_all"] == 3
    assert out["llm_any"] == 1  # a counted once; mcp-only b and old project not counted


def test_mcp_names_recent_only():
    con = build(
        [("old", "2024-01-01", 0), ("a", "2026-03-05", 0)],
        [("a", "mcp.server", "mcp"), ("old", "mcp.server", "mcp"), ("a", "mcp.ClientSession", "mcp")],
    )
    assert analyse(con)["mcp_names"] == [["mcp.server", 1], ["mcp.server.fastmcp.FastMCP", 0],
                                         ["mcp.ClientSession", 1]]


def test_mcp_client_counts_either_name_once():
    con = build(
        [("old", "2024-01-01", 0), ("a", "2026-03-05", 0), ("b", "2026-03-05", 0), ("c", "2026-03-05", 0)],
        [("a", "mcp.client", "mcp"), ("a", "mcp.ClientSession", "mcp"), ("b", "mcp.ClientSession", "mcp"),
         ("c", "mcp.server", "mcp"), ("old", "mcp.client", "mcp")],
    )
    assert analyse(con)["mcp_client"] == 2
