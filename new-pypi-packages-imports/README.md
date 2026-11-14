# What new PyPI packages are made of

Code and results for the post [What new PyPI packages are made of](https://py-code.org/blog/new-pypi-packages-imports/): the October 2026 jump in new projects, which LLM SDKs new packages import, requests vs httpx vs aiohttp, and pydantic v1 vs v2 validators.

Data: the py-code.org dataset as of **13 November 2026**, Hugging Face revision `9d81d70d6519d77f4dee4811b3e3a5d88379c17d`. 354,763 projects, latest release only.

## Reproduce every number

```
pip install duckdb
python3 blog_data.py
```

This reads the pinned snapshot from Hugging Face and writes `out/new-packages.json` and the chart SVGs to `out/new-packages/`. Compare `out/new-packages.json` with [`results/new-packages.json`](results/new-packages.json): they should be identical. Every number in the post comes from that file.

To run it on a local copy of the Parquet files instead: `python3 blog_data.py <parquet-folder> <out-folder>`.

## Files

| File | What it does |
|---|---|
| `blog_data.py` | All the queries (`SQL_MONTHS`, `SQL_SDKS`, `SQL_HTTP`, `SQL_PYDANTIC` and others) and the chart calls. |
| `svgchart.py` | Draws the bar and column charts as SVG. Colours are the site's CSS variables, so the SVGs render without colour outside the site. |
| `october_check.py` | Checks whether the October jump is real: samples projects per month and asks PyPI's JSON API for each one's first upload. |
| `sdks-query.sql` | The single DuckDB query shown in the post. Paste it into the DuckDB shell. |
| `test_*.py` | Tests for the counting rules, such as counting a project once when it imports several SDKs. Run with `pytest`. |
| `results/` | The JSON and charts used in the post. |

## The October check

```
python3 october_check.py --sample 300
```

It makes one request to PyPI every 0.2 seconds, so it takes a few minutes. The sample is fixed (ordered by a hash of the project name), but PyPI's answers can change if a project deletes old releases, so a rerun may differ slightly from [`results/october_check.json`](results/october_check.json).

## How the numbers were counted

- **Latest release only.** The index holds the latest release of each project, so a month's count is projects whose latest release came out that month, not uploads.
- **Static imports only.** The scanner reads import statements and attribute access on imported names. Imports through `importlib` or `__import__`, and names reached through variables, are missed. A project's own modules are never counted.
- **No filtering.** Every project with a release in the year counts, including test uploads and very small packages.
- **Recent projects.** The SDK and month numbers use projects released on or after 13 November 2025. The requests/httpx and pydantic numbers use every indexed project, and also give a share weighted by downloads.
- **Downloads.** Download counts are for the 30 days before the scan, from ClickHouse's public PyPI dataset, and exist only for the 60,000 most downloaded projects.
