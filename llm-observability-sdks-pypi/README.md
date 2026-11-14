# The LLM observability SDKs that PyPI projects actually import

Code and results for the post [The LLM observability SDKs that PyPI projects actually import](https://py-code.org/blog/llm-observability-sdks-pypi/). It counts the PyPI projects whose code imports each LLM observability SDK and each AI agent framework. The same script produces the numbers for both posts in this series: [LLM observability SDKs](https://py-code.org/blog/llm-observability-sdks-pypi/) and [AI agent frameworks](https://py-code.org/blog/ai-agent-frameworks-pypi/).

Data: the py-code.org dataset as of **13 November 2026**, Hugging Face revision `9d81d70d6519d77f4dee4811b3e3a5d88379c17d`. 354,763 projects, latest release only.

## Reproduce every number

```
pip install duckdb
python3 ai_tools_data.py
```

This reads the pinned snapshot from Hugging Face and writes `out/ai-tools.json` and the two bar charts to `out/ai-tools/`. Compare `out/ai-tools.json` with [`results/ai-tools.json`](results/ai-tools.json): they should be identical. Every number in the posts comes from that file.

To run it on a local copy of the Parquet files instead: `python3 ai_tools_data.py <parquet-folder> <out-folder>`.

## Files

| File | What it does |
|---|---|
| `ai_tools_data.py` | The rule for each tool (modules and dotted names), the counts, the overlaps between tools and the charts. |
| `openai_agents_names.txt` | The public names of the OpenAI Agents SDK (`__all__` in `agents/__init__.py`, openai-agents 0.24.0). |
| `pypistats_fetch.py` | Fetches each package's downloads in the last month from pypistats.org into `results/pypistats.json`. |
| `release_dates.py` | Fetches each package's first upload date from PyPI into `results/first_release.json`. |
| `svgchart.py` | Draws the bar charts as SVG. Colours are the site's CSS variables. |
| `query.sql` | The DuckDB query shown in the post. |
| `test_ai_tools_data.py` | Tests for the matching rules. Run with `pytest`. |
| `results/` | `ai-tools.json`, `pypistats.json`, `first_release.json` and, in `charts/`, the charts used in the posts. |

## How the numbers were counted

- **Which projects.** The index holds the latest release of every project released between 13 November 2025 and 13 November 2026, plus the 60,000 most downloaded projects.
- **Using a tool.** A project uses a tool when its code imports one of the tool's modules (for example `langfuse`, or any `langchain_*` module for LangChain) or a dotted name under one of its prefixes (for example `google.adk`, or `mlflow.trace` and `mlflow.openai.autolog` for MLflow Tracing). The exact lists are at the top of `ai_tools_data.py`. Imports in tests and examples count.
- **OpenAI Agents SDK.** It imports as `agents`, a name many projects use for their own folder, so a project counts only when it imports one of the SDK's public names, less generic ones such as `Agent` and `Tool`.
- **Own packages.** The headline count (`third_party`) leaves out projects whose normalised name is the tool's own name or starts with it followed by `-` (for example `langchain-*`, `crewai-*`, `openinference-*`). `projects` includes them.
- **Copies.** The 2,144 `iflow-mcp*` projects are copies of other people's MCP servers under one prefix and are dropped everywhere.
- **Downloads.** `package_downloads_month` is pypistats.org's last-month count, fetched on 14 November 2026. `top60k` counts projects among the index's 60,000 most downloaded, a ranking that comes from ClickHouse's public PyPI dataset.
- **Overlaps.** `frameworks_with_obs` and `obs_with_frameworks` count, among a tool's projects (own packages left out), those that also import tools of the other kind. `pairs` and `langchain_langgraph` use all projects.
