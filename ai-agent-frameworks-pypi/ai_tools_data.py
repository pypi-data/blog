"""Which LLM observability SDKs and AI agent frameworks PyPI projects import.

Counts, for each tool, the projects in the py-code.org index whose code imports it,
from refs.parquet (one row per project and imported name). Writes one JSON file per
post and the charts.

    python3 ai_tools_data.py [<parquet-folder>] [<out-folder>]

With no folder it reads the current dataset from Hugging Face. It is rebuilt weekly, so the
numbers drift from the posts'.
"""
import json
import sys
from pathlib import Path

HF_SNAPSHOT = "hf://datasets/pypi-data/py-code"
SNAPSHOT_DATE = "2026-11-13"

# Republished copies of other people's MCP servers under one prefix (2,160 projects).
# They would count every framework those servers import a second time.
COPY_FAMILIES = ["iflow-mcp"]

# The OpenAI Agents SDK installs as openai-agents but imports as `agents`, a name many
# projects also use for their own folder. A project counts only when it imports one of
# the SDK's public names (agents/__init__.py __all__ in openai-agents 0.24.0), less the
# generic ones below. See openai_agents_names.txt.
OPENAI_AGENTS_GENERIC = {"Agent", "AgentBase", "Model", "ModelProvider", "Tool", "Environment",
                         "Button", "Computer", "AsyncComputer", "Usage", "Prompt", "Session"}

OPENLLMETRY_INSTRUMENTATIONS = [
    "openai", "anthropic", "langchain", "llamaindex", "bedrock", "cohere", "vertexai",
    "google_generativeai", "mistralai", "groq", "ollama", "together", "replicate",
    "transformers", "chromadb", "pinecone", "qdrant", "weaviate", "milvus", "lancedb",
    "haystack", "crewai", "mcp", "openai_agents", "watsonx", "sagemaker", "alephalpha",
    "writer", "agno", "marqo", "voyageai"]
MLFLOW_GENAI = ["openai", "langchain", "llama_index", "anthropic", "dspy", "crewai", "autogen",
                "litellm", "gemini", "bedrock", "groq", "mistral", "pydantic_ai", "smolagents",
                "agno", "strands", "openai_agents", "ag2", "semantic_kernel", "haystack"]

# name: (category, pypi package, modules, name prefixes, own-family project prefixes)
# A project uses a tool when it imports one of `modules` (the top-level module) or a
# dotted name that starts with one of `prefixes`.
OBSERVABILITY = {
    "Langfuse": ("langfuse", ["langfuse"], [], ["langfuse"]),
    "LangSmith": ("langsmith", ["langsmith"], [], ["langsmith"]),
    "Pydantic Logfire": ("logfire", ["logfire"], [], ["logfire"]),
    "Arize Phoenix / OpenInference": ("openinference-semantic-conventions", ["openinference", "arize"],
        ["phoenix.otel", "phoenix.client", "phoenix.evals", "phoenix.trace", "phoenix.experiments",
         "phoenix.launch_app", "phoenix.session"], ["arize", "openinference"]),
    "MLflow Tracing": ("mlflow", [],
        ["mlflow.tracing", "mlflow.trace", "mlflow.start_span", "mlflow.get_current_active_span",
         "mlflow.update_current_trace", "mlflow.get_trace", "mlflow.search_traces", "mlflow.genai",
         "mlflow.entities.SpanType", "mlflow.entities.Span", "mlflow.entities.Trace"]
        + [f"mlflow.{f}.autolog" for f in MLFLOW_GENAI], ["mlflow"]),
    "OpenLLMetry (Traceloop)": ("traceloop-sdk", ["traceloop"],
        [f"opentelemetry.instrumentation.{i}" for i in OPENLLMETRY_INSTRUMENTATIONS],
        ["traceloop", "opentelemetry-instrumentation"]),
    "W&B Weave": ("weave", ["weave"], [], ["weave"]),
    "Comet Opik": ("opik", ["opik"], [], ["opik"]),
    "Braintrust": ("braintrust", ["braintrust"], [], ["braintrust", "autoevals"]),
    "AgentOps": ("agentops", ["agentops"], [], ["agentops"]),
    "Laminar": ("lmnr", ["lmnr"], [], ["lmnr"]),
    "LangWatch": ("langwatch", ["langwatch"], [], ["langwatch"]),
    "OpenLIT": ("openlit", ["openlit"], [], ["openlit"]),
    "Lunary": ("lunary", ["lunary"], [], ["lunary"]),
    "Literal AI": ("literalai", ["literalai"], [], ["literalai"]),
    "TruLens": ("trulens", ["trulens", "trulens_eval"], [], ["trulens"]),
    "PromptLayer": ("promptlayer", ["promptlayer"], [], ["promptlayer"]),
    "Datadog LLM Observability": ("ddtrace", [], ["ddtrace.llmobs"], ["ddtrace"]),
    "HoneyHive": ("honeyhive", ["honeyhive"], [], ["honeyhive"]),
    "Galileo": ("galileo", ["galileo", "promptquality"], [], ["galileo", "promptquality"]),
    "Langtrace": ("langtrace-python-sdk", ["langtrace_python_sdk"], [], ["langtrace"]),
    "Helicone": ("helicone", ["helicone"], [], ["helicone"]),
}
GATEWAYS_AND_EVALS = {
    "Portkey": ("portkey-ai", ["portkey_ai"], [], ["portkey"]),
    "Ragas": ("ragas", ["ragas"], [], ["ragas"]),
    "DeepEval": ("deepeval", ["deepeval"], [], ["deepeval"]),
}
FRAMEWORKS = {
    "LangChain": ("langchain", ["langchain*"], [], ["langchain"]),
    "LangGraph": ("langgraph", ["langgraph"], [], ["langgraph"]),
    "CrewAI": ("crewai", ["crewai"], [], ["crewai"]),
    "Pydantic AI": ("pydantic-ai", ["pydantic_ai"], [], ["pydantic-ai"]),
    "LlamaIndex": ("llama-index-core", [], ["llama_index"], ["llama-index", "llamaindex"]),
    "Claude Agent SDK": ("claude-agent-sdk", ["claude_agent_sdk", "claude_code_sdk"], [],
                         ["claude-agent-sdk", "claude-code-sdk"]),
    "OpenAI Agents SDK": ("openai-agents", [], [], ["openai-agents"]),
    "Google ADK": ("google-adk", [], ["google.adk"], ["google-adk"]),
    "AutoGen (Microsoft)": ("autogen-agentchat", ["autogen_agentchat", "autogen_core", "autogen_ext"], [],
                            ["autogen", "pyautogen"]),
    "AG2 and classic AutoGen": ("ag2", ["ag2", "autogen"], [], ["ag2", "autogen"]),
    "Haystack": ("haystack-ai", ["haystack", "haystack_experimental", "haystack_integrations"], [],
                 ["haystack"]),
    "Strands Agents": ("strands-agents", ["strands"], [], ["strands"]),
    "DSPy": ("dspy", ["dspy"], [], ["dspy"]),
    "Deep Agents": ("deepagents", ["deepagents"], [], ["deepagents"]),
    "Agno": ("agno", ["agno"], [], ["agno"]),
    "Microsoft Agent Framework": ("agent-framework", ["agent_framework"], [], ["agent-framework"]),
    "smolagents": ("smolagents", ["smolagents"], [], ["smolagents"]),
    "Semantic Kernel": ("semantic-kernel", ["semantic_kernel"], [], ["semantic-kernel"]),
    "AgentScope": ("agentscope", ["agentscope"], [], ["agentscope"]),
    "CAMEL": ("camel-ai", ["camel"], [], ["camel"]),
    "Letta": ("letta", ["letta", "letta_client"], [], ["letta"]),
    "Burr": ("burr", ["burr"], [], ["burr"]),
    "Griptape": ("griptape", ["griptape"], [], ["griptape"]),
    "Langroid": ("langroid", ["langroid"], [], ["langroid"]),
    "MetaGPT": ("metagpt", ["metagpt"], [], ["metagpt"]),
}
LLM_SDKS = {
    "OpenAI SDK": ("openai", ["openai"], [], ["openai"]),
    "Anthropic SDK": ("anthropic", ["anthropic"], [], ["anthropic"]),
    "LiteLLM": ("litellm", ["litellm"], [], ["litellm"]),
    "MCP SDK": ("mcp", ["mcp"], [], ["mcp"]),
}
# Downloads in the last month from pypistats.org, fetched on 14 Nov 2026 by
# pypistats_fetch.py. The index's own 30-day counts (from ClickHouse's public PyPI demo)
# rank the 60,000 most downloaded projects, but are several times lower than pypistats
# for some packages, so the posts quote pypistats.
PYPISTATS = {}

# How projects call an SDK: projects (outside the copy families) importing any of these names.
NAME_COUNTS = {
    "langfuse.langchain": ["langfuse.langchain", "langfuse.callback"],
    "langfuse.openai": ["langfuse.openai"],
    "langfuse.observe": ["langfuse.observe", "langfuse.decorators.observe"],
    "logfire.instrument_pydantic_ai": ["logfire.instrument_pydantic_ai"],
}

GROUPS = {"observability": OBSERVABILITY, "gateways_evals": GATEWAYS_AND_EVALS,
          "frameworks": FRAMEWORKS, "llm_sdks": LLM_SDKS}


def _norm(name):
    return name.lower().replace("_", "-").replace(".", "-")


def _sql_list(values):
    return ", ".join("'" + v.replace("'", "''") + "'" for v in values) or "NULL"


def usage_sql(tool, spec, agents_names):
    """SELECT project, tool for every project that uses the tool."""
    _, modules, prefixes, _ = spec
    conds = []
    exact = [m for m in modules if not m.endswith("*")]
    if exact:
        conds.append(f"module IN ({_sql_list(exact)})")
    for m in modules:
        if m.endswith("*"):
            conds.append(f"starts_with(module, '{m[:-1]}')")
    for p in prefixes:
        conds.append(f"(name = '{p}' OR starts_with(name, '{p}.'))")
    if tool == "OpenAI Agents SDK":
        conds.append(f"(module = 'agents' AND split_part(name, '.', 2) IN ({_sql_list(agents_names)}))")
    return f"SELECT DISTINCT project, '{tool}' AS tool FROM r WHERE " + " OR ".join(conds)


def is_family(project, spec):
    n = _norm(project)
    return any(n == f or n.startswith(f + "-") for f in spec[3])


def analyse(con, agents_names):
    tools = {t: (g, s) for g, specs in GROUPS.items() for t, s in specs.items()}
    con.execute("CREATE TEMP TABLE u (project VARCHAR, tool VARCHAR)")
    for t, (_, spec) in tools.items():
        con.execute("INSERT INTO u " + usage_sql(t, spec, agents_names))
    copies = " OR ".join(f"starts_with(lower(project), '{c}')" for c in COPY_FAMILIES)
    dropped = con.execute(f"SELECT count(DISTINCT project) FROM p WHERE {copies}").fetchone()[0]
    con.execute(f"DELETE FROM u WHERE {copies}")
    rows = con.execute("""SELECT u.project, u.tool, p.downloads_30d, CAST(p.upload_time AS DATE)
                          FROM u JOIN p USING (project)""").fetchall()
    by_tool, by_project, info = {}, {}, {}
    for project, tool, dl, up in rows:
        by_tool.setdefault(tool, set()).add(project)
        by_project.setdefault(project, set()).add(tool)
        info[project] = (dl, up.isoformat())
    pkg_dl = dict(con.execute("SELECT lower(project), downloads_30d FROM p").fetchall())
    months = con.execute("""SELECT strftime(upload_time, '%Y-%m') m, count(*) FROM p
                            WHERE upload_time >= '2025-11-01' AND upload_time < '2026-11-01'
                            GROUP BY 1 ORDER BY 1""").fetchall()

    def tool_row(t):
        group, spec = tools[t]
        users = by_tool.get(t, set())
        third = {p for p in users if not is_family(p, spec)}
        month_counts = {}
        for p in users:
            month_counts[info[p][1][:7]] = month_counts.get(info[p][1][:7], 0) + 1
        return {"tool": t, "group": group, "package": spec[0],
                "projects": len(users), "third_party": len(third), "own_family": len(users) - len(third),
                "top60k": sum(1 for p in third if info[p][0]),
                "package_downloads_30d": pkg_dl.get(spec[0]),
                "package_downloads_month": PYPISTATS.get(_norm(spec[0])),
                "by_month": {m: month_counts.get(m, 0) for m, _ in months}}

    out = {"snapshot": SNAPSHOT_DATE, "hf_revision": HF_SNAPSHOT.split("@")[1],
           "projects_all": con.execute("SELECT count(*) FROM p").fetchone()[0],
           "copies_dropped": dropped,
           "projects_by_month": dict(months),
           "tools": {g: sorted((tool_row(t) for t in specs), key=lambda x: (-x["third_party"], x["tool"]))
                     for g, specs in GROUPS.items()}}

    # OpenInference (Arize's instrumentation libraries) and Phoenix (Arize's app) share one
    # row; say how many of its projects import each.
    arize_spec = tools["Arize Phoenix / OpenInference"][1]
    arize = {p for p in by_tool.get("Arize Phoenix / OpenInference", set()) if not is_family(p, arize_spec)}
    oi = {row[0] for row in con.execute(
        "SELECT DISTINCT project FROM r WHERE module = 'openinference'").fetchall()} & arize
    out["arize_split"] = {"openinference": len(oi), "without_openinference": len(arize - oi)}

    mcp_named = {row[0] for row in con.execute(f"""
        SELECT project FROM p WHERE project IN (SELECT project FROM u WHERE tool = 'MCP SDK')
          AND (lower(project) LIKE '%mcp%' OR lower(summary) LIKE '%mcp%'
               OR lower(summary) LIKE '%model context protocol%')""").fetchall()}
    out["name_counts"] = {}
    for key, names in NAME_COUNTS.items():
        conds = " OR ".join(f"name = '{n}' OR starts_with(name, '{n}.')" for n in names)
        out["name_counts"][key] = con.execute(
            f"SELECT count(DISTINCT project) FROM r WHERE ({conds}) AND NOT ({copies})").fetchone()[0]

    def any_of(group, exclude_family_of=None):
        names = set(GROUPS[group])
        return {p for p, ts in by_project.items() if ts & names}

    obs = any_of("observability")
    fw = any_of("frameworks")
    llm = any_of("llm_sdks") - {p for p, ts in by_project.items() if ts == {"MCP SDK"}}
    out["totals"] = {
        "observability_any": len(obs), "frameworks_any": len(fw),
        "llm_sdk_any": len(llm), "openai_or_anthropic": len(
            {p for p, ts in by_project.items() if ts & {"OpenAI SDK", "Anthropic SDK"}}),
        "llm_or_framework": len(llm | fw),
        "llm_or_framework_with_obs": len((llm | fw) & obs),
        "framework_with_obs": len(fw & obs),
        "openai_or_anthropic_no_framework": len(
            {p for p, ts in by_project.items() if ts & {"OpenAI SDK", "Anthropic SDK"}} - fw),
        "framework_and_llm_sdk": len(fw & llm),
    }
    # Which frameworks and SDKs the users of each observability tool also import, and
    # the reverse: which observability tool each framework's users pick.
    def third(t):
        return {p for p in by_tool.get(t, set()) if not is_family(p, tools[t][1])}

    def cross(a_group, b_group, top_a):
        res = {}
        for row in out["tools"][a_group][:top_a]:
            users = third(row["tool"])
            counts, with_any = {}, 0
            for p in users:
                hits = [t for t in by_project[p] & set(GROUPS[b_group]) if not is_family(p, tools[t][1])]
                with_any += bool(hits)
                for t in hits:
                    counts[t] = counts.get(t, 0) + 1
            res[row["tool"]] = {"users": len(users), "with_any": with_any,
                                "top": sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:5]}
        return res
    out["obs_with_frameworks"] = cross("observability", "frameworks", 8)
    out["frameworks_with_obs"] = cross("frameworks", "observability", 10)
    out["obs_with_llm_sdks"] = cross("observability", "llm_sdks", 8)
    # LangChain users that also import LangGraph, and the share of LangGraph users that import LangChain.
    # Like every count in the posts, these leave out each tool's own packages.
    lc, lg = third("LangChain"), third("LangGraph")
    out["langchain_langgraph"] = {"langchain": len(lc), "langgraph": len(lg), "both": len(lc & lg),
                                  "langgraph_without_langchain": len(lg - lc)}
    pairs = [("LangChain", "LlamaIndex"), ("LangChain", "CrewAI"), ("LangChain", "Pydantic AI"),
             ("LangGraph", "CrewAI"), ("LangGraph", "Pydantic AI"), ("LangGraph", "OpenAI Agents SDK"),
             ("LangGraph", "Google ADK"), ("CrewAI", "AutoGen (Microsoft)"), ("LangChain", "Deep Agents"),
             ("LangGraph", "Deep Agents"), ("Claude Agent SDK", "OpenAI Agents SDK")]
    out["pairs"] = {f"{a}+{b}": len(third(a) & third(b)) for a, b in pairs}
    out["totals_mcp_named"] = len(mcp_named & third("MCP SDK"))
    out["autogen_either"] = len(third("AutoGen (Microsoft)") | third("AG2 and classic AutoGen"))
    fw_counts = {}
    for p in fw:
        k = len(by_project[p] & set(FRAMEWORKS))
        fw_counts[k] = fw_counts.get(k, 0) + 1
    out["frameworks_per_project"] = dict(sorted(fw_counts.items()))
    return out


def write_charts(r, out):
    from svgchart import hbar
    d = out / "ai-tools"
    d.mkdir(parents=True, exist_ok=True)
    obs = [t for t in r["tools"]["observability"] if t["third_party"]][:12]
    (d / "observability.svg").write_text(hbar(
        [(t["tool"].split(" (")[0].replace(" / OpenInference", ""), t["third_party"]) for t in obs],
        unit="projects that import it",
        title="LLM observability SDKs imported by PyPI projects"))
    fw = [t for t in r["tools"]["frameworks"]][:14]
    (d / "frameworks.svg").write_text(hbar(
        [(t["tool"], t["third_party"]) for t in fw],
        unit="projects that import it",
        title="AI agent frameworks imported by PyPI projects"))


def main(argv):
    import duckdb
    here = Path(__file__).resolve().parent
    parquet = (argv[1] if len(argv) > 1 else HF_SNAPSHOT).rstrip("/")
    out = Path(argv[2] if len(argv) > 2 else "out")
    stats = here / "results" / "pypistats.json"
    if stats.exists():
        PYPISTATS.update({_norm(k): v for k, v in json.loads(stats.read_text())["last_month"].items()
                          if v is not None})
    names = [n for n in (here / "openai_agents_names.txt").read_text().split()
             if n not in OPENAI_AGENTS_GENERIC]
    con = duckdb.connect()
    con.execute(f"CREATE VIEW p AS SELECT * FROM read_parquet('{parquet}/projects.parquet')")
    con.execute(f"CREATE VIEW r AS SELECT project, name, module FROM read_parquet('{parquet}/refs.parquet')")
    result = analyse(con, names)
    out.mkdir(parents=True, exist_ok=True)
    (out / "ai-tools.json").write_text(json.dumps(result, indent=1) + "\n")
    write_charts(result, out)
    for g, rows in result["tools"].items():
        print(g)
        for t in rows:
            print(f'  {t["tool"]:32} {t["projects"]:6} {t["third_party"]:6} top60k {t["top60k"]:5} '
                  f'pkg {t["package_downloads_month"]}')
    print(json.dumps({k: result[k] for k in ("totals", "langchain_langgraph", "frameworks_per_project",
                                             "copies_dropped")}, indent=1))


if __name__ == "__main__":
    main(sys.argv)
