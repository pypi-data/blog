# PyPI code that breaks on Python 3.12 and 3.13

Code and results for the post [PyPI code that breaks on Python 3.12 and 3.13](https://py-code.org/blog/removed-stdlib-modules-pypi/): which PyPI projects still import the 25 standard-library modules removed in Python 3.12 (`distutils`, `imp`, `asyncore`, `asynchat`, `smtpd`) and 3.13 (the 19 PEP 594 modules and `lib2to3`), and whether those imports would fail.

Data: the py-code.org dataset as of **13 November 2026**: 354,763 projects, latest release only. The dataset is rebuilt every week and Hugging Face keeps no older versions, so the 13 November data is no longer online. `results/` holds what the scripts gave on it.

## Reproduce every number

```
pip install duckdb
python3 removed_data.py
```

This reads the current dataset from Hugging Face and [`results/checks.jsonl`](results/checks.jsonl), and writes `out/removed.json` and the chart SVGs to `out/removed-modules/`. Compare `out/removed.json` with [`results/removed.json`](results/removed.json): the numbers differ by however much the index has changed since 13 November 2026. Every number in the post comes from that file.

To run it on a local copy of the Parquet files instead: `python3 removed_data.py <parquet-folder> results/checks.jsonl <out-folder>`.

## Redo the import check

`results/checks.jsonl` comes from `removed_check.py`, which downloads each project's release file again (the same file the index scanned) and parses every `.py` file with `ast`, without running it. To redo it:

```
pip install duckdb requests
python3 -c "import duckdb; duckdb.sql(\"COPY (SELECT project, version, file FROM 'hf://datasets/pypi-data/py-code/projects.parquet' WHERE project IN (SELECT project FROM 'hf://datasets/pypi-data/py-code/refs.parquet' WHERE name = module AND module IN ('distutils','imp','asyncore','asynchat','smtpd','aifc','audioop','cgi','cgitb','chunk','crypt','imghdr','lib2to3','mailcap','msilib','nis','nntplib','ossaudiodev','pipes','sndhdr','spwd','sunau','telnetlib','uu','xdrlib'))) TO 'projects.tsv' (DELIMITER '\t', HEADER false)\")"
python3 removed_check.py projects.tsv checks.jsonl --workers 8
```

It downloads only the `.py` files of wheels (with HTTP range requests) and whole source archives otherwise. It can be stopped and restarted; finished projects are skipped. PyPI can delete files, so a rerun may differ slightly.

## Files

| File | What it does |
|---|---|
| `removed_check.py` | Finds every import of a removed module in a project's release and labels it: `module` (top level, unguarded), `function` (inside a function, unguarded), `guarded` (in `try` with an `ImportError`, `ModuleNotFoundError` or `Exception` handler), `fallback` (in an `except` block) or `gated` (under an `if` that tests the Python version). It also labels the file as code, test, setup or docs. |
| `removed_data.py` | Counts projects per module and per label, ranks projects by downloads, and draws the charts and the results card. |
| `svgchart.py` | Draws the bar charts and the card as SVG. Colours are the site's CSS variables, so the SVGs render without colour outside the site. |
| `query.sql` | The DuckDB query shown in the post. |
| `test_*.py` | Tests for the labelling rules. Run with `pytest`. |
| `results/` | `checks.jsonl` (the import check), `removed.json` and the charts used in the post. |

## How the numbers were counted

- **Which projects.** Every project whose code imports one of the 25 modules by name in the py-code.org index. The index holds the latest release of every project released between 13 November 2025 and 13 November 2026, plus the 60,000 most downloaded projects.
- **Unguarded.** A project counts as unguarded when its own code (not tests, `setup.py`, docs or examples) has an import labelled `module` or `function`. This is a rule, not a test: a guarded import whose fallback is also missing (pydub's `pyaudioop`) counts as safe, and an unguarded import in a file that never loads on a new Python (pip's `_distutils.py`) counts as unguarded.
- **Dependencies.** An import is not counted when the project declares a copy of the module as a required dependency: `legacy-cgi`, `audioop-lts`, `zombie-imp`, `pyasyncore`, `pyasynchat`, `crypt-r`, any `standard-<module>` package, or `setuptools` for `distutils`. setuptools itself, which ships `distutils`, is not counted for it.
- **Stale.** "No release in two years" means the latest release was uploaded before 13 November 2024.
- **Downloads.** Download counts are for the 30 days before the scan, from ClickHouse's public PyPI dataset, and exist only for the 60,000 most downloaded projects.
