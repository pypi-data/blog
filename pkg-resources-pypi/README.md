# PyPI packages that still import pkg_resources

Code and results for the post [setuptools removed pkg_resources. 1,504 PyPI packages still need it](https://py-code.org/blog/pkg-resources-pypi/): which PyPI projects still use `pkg_resources`, which setuptools 82.0.0 removed on 8 February 2026, and whether each import would fail without it.

Data: the py-code.org dataset as of **13 November 2026**: 354,763 projects, latest release only. The dataset is rebuilt every week and Hugging Face keeps no older versions, so the 13 November data is no longer online. `results/` holds what the scripts gave on it.

## Send a fix

[`results/unguarded.csv`](results/unguarded.csv) lists every project whose own code imports `pkg_resources` with no guard: its downloads in the 30 days before the scan, its latest release date, whether the riskiest import is at the top of a file (`module`) or inside a function (`function`), the file and line of each such import, and its repository when PyPI names one. Check the project's main branch and open pull requests before you send one: this list comes from the latest release on PyPI.

## Reproduce every number

```
pip install duckdb packaging
python3 pkg_data.py
```

This reads the current dataset from Hugging Face and [`results/checks.jsonl`](results/checks.jsonl), and writes `out/pkg.json`, `out/unguarded.csv` and the chart SVGs to `out/pkg-resources/`. Compare `out/pkg.json` with [`results/pkg.json`](results/pkg.json): the numbers differ by however much the index has changed since 13 November 2026. Every number in the post comes from that file.

To run it on a local copy of the Parquet files instead: `python3 pkg_data.py <parquet-folder> results/checks.jsonl <out-folder>`.

## Redo the import check

`results/checks.jsonl` comes from `pkg_check.py`, which downloads each project's release file again (the same file the index scanned) and parses every `.py` file with `ast`, without running it. To redo it:

```
pip install duckdb requests
python3 -c "import duckdb; duckdb.sql(\"COPY (SELECT project, version, file FROM 'hf://datasets/pypi-data/py-code/projects.parquet' WHERE project IN (SELECT project FROM 'hf://datasets/pypi-data/py-code/refs.parquet' WHERE name = 'pkg_resources') ORDER BY project) TO 'projects.tsv' (DELIMITER '\t', HEADER false)\")"
python3 pkg_check.py projects.tsv checks.jsonl --workers 16
```

It downloads only the `.py` files of wheels (with HTTP range requests) and whole source archives otherwise. It can be stopped and restarted; finished projects are skipped. PyPI can delete files, so a rerun may differ slightly: one project (`embedxpl`) was already gone when we ran it.

## Files

| File | What it does |
|---|---|
| `pkg_check.py` | Finds every import of `pkg_resources` in a project's release (`import`, `from … import`, `__import__("pkg_resources")`, `importlib.import_module("pkg_resources")`) and labels it: `module` (top level, unguarded), `function` (inside a function, unguarded), `guarded` (in `try` with an `ImportError`, `ModuleNotFoundError` or `Exception` handler, or in `with suppress(…)` with one of those), `fallback` (in an `except` block), `gated` (under an `if` that tests the Python version) or `loaded` (under an `if` that checks `"pkg_resources" in sys.modules` or uses `find_spec`). It also records the file kind (code, test, setup, docs), the release's Requires-Dist and its project URLs. |
| `pkg_data.py` | Classifies each project by its riskiest import, counts projects per class and per `pkg_resources` name, ranks the unguarded projects by downloads, and writes `unguarded.csv`, the charts and the results card. |
| `svgchart.py` | Draws the bar charts and the card as SVG. Colours are the site's CSS variables, so the SVGs render without colour outside the site. |
| `query.sql` | The DuckDB query shown in the post. |
| `test_*.py` | Tests for the labelling rules. Run with `pytest`. |
| `results/` | `checks.jsonl` (the import check), `pkg.json`, `unguarded.csv`, the query output and the charts used in the post. |

## How the numbers were counted

- **Which projects.** Every project whose code uses `pkg_resources` by name in the py-code.org index, except setuptools itself. The index holds the latest release of every project released between 13 November 2025 and 13 November 2026, plus the 60,000 most downloaded projects. The index does not follow `__import__()`, so a project whose only use is `__import__("pkg_resources")` is not in the list.
- **Classes.** A project's class is its riskiest import in its own code: `module`, then `function`, then `safe` (every import guarded, a fallback, gated or loaded). Projects with an unguarded import count as `pinned` when a required (non-extra) dependency is `setuptools` with a version range that excludes 82.0.0, or `pkg-resources-backport`. Projects whose only unguarded imports are in bundled copies (folders such as `_vendor`, `vendored`, `_vendored_packages`, `inline_copy`, `third_party`, `extern`, `node_modules`) count as `vendored`. Projects with imports only in `setup.py` or build scripts count as `setup`, and only in tests or docs, or not found again, as `other`.
- **Own code.** Files under `test`, `tests`, `_tests` and `testing` folders, `test_*.py`, `*_test.py`, `conftest.py`, docs, examples, benchmarks and files named `benchmark*` are not the project's own code. File kinds are recomputed from the path in `pkg_data.py`, so `checks.jsonl` keeps the raw labels.
- **A rule, not a test.** An unguarded import in a file that never loads counts as unguarded, and so does one in a branch that a setting or a missing library turns off (pbr's `METADATA_LIB_LEGACY` branch, PyInstaller's `pkg_resources` runtime hook). The post reads the most downloaded cases by hand.
- **Dates.** "After the removal" means uploaded on or after 8 February 2026 (setuptools 82.0.0 on PyPI). "Active" means on or after 13 May 2026. "No release in two years" means before 13 November 2024.
- **Repository.** The first project URL on GitHub, GitLab, Codeberg, Bitbucket or sourcehut, preferring the ones labelled Source, Repository or Code.
- **Downloads.** Download counts are for the 30 days before the scan, from ClickHouse's public PyPI dataset, and exist only for the 60,000 most downloaded projects.
