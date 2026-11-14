import duckdb

from ai_tools_data import FRAMEWORKS, OBSERVABILITY, is_family, usage_sql


def con_with(rows):
    con = duckdb.connect()
    con.execute("CREATE TABLE r (project VARCHAR, name VARCHAR, module VARCHAR)")
    con.executemany("INSERT INTO r VALUES (?, ?, ?)", rows)
    return con


def users(con, tool, spec, names=()):
    return sorted(p for p, _ in con.execute(usage_sql(tool, spec, list(names))).fetchall())


def test_langchain_matches_every_langchain_module():
    con = con_with([("a", "langchain_core.messages", "langchain_core"),
                    ("b", "langchain_openai", "langchain_openai"),
                    ("c", "langgraph.graph", "langgraph")])
    assert users(con, "LangChain", FRAMEWORKS["LangChain"]) == ["a", "b"]


def test_name_prefix_does_not_match_a_longer_name():
    con = con_with([("a", "google.adk.agents", "google"), ("b", "google.adkx", "google"),
                    ("c", "google.genai", "google")])
    assert users(con, "Google ADK", FRAMEWORKS["Google ADK"]) == ["a"]


def test_openai_agents_needs_a_public_name():
    con = con_with([("sdk", "agents.Runner", "agents"), ("own", "agents.base.Agent", "agents"),
                    ("generic", "agents.Agent", "agents")])
    assert users(con, "OpenAI Agents SDK", FRAMEWORKS["OpenAI Agents SDK"], ["Runner"]) == ["sdk"]


def test_mlflow_tracing_ignores_experiment_tracking():
    con = con_with([("a", "mlflow.start_run", "mlflow"), ("b", "mlflow.openai.autolog", "mlflow"),
                    ("c", "mlflow.trace", "mlflow")])
    assert users(con, "MLflow Tracing", OBSERVABILITY["MLflow Tracing"]) == ["b", "c"]


def test_family_is_name_prefix_with_separator():
    spec = FRAMEWORKS["CrewAI"]
    assert is_family("crewai-tools", spec) and is_family("CrewAI_Tools", spec) and is_family("crewai", spec)
    assert not is_family("crewaix", spec) and not is_family("my-crewai", spec)
