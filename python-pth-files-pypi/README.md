# PyPI packages that run code every time Python starts

Code and results for the post [PyPI packages that run code every time Python starts](https://py-code.org/blog/python-pth-files-pypi/): which PyPI projects ship a `.pth` file with an `import` line, what that line does, whether Python actually runs it after a normal install, and which projects already ship a PEP 829 `.start` file.

Data: the py-code.org dataset as of **13 November 2026**: 354,763 projects, latest release only. The dataset is rebuilt every week and Hugging Face keeps no older versions, so the 13 November data is no longer online. `results/` holds what the scripts gave on it.

## Reproduce every number

```
pip install duckdb
python3 pth_data.py
```

This reads the current dataset from Hugging Face and [`results/checks.jsonl`](results/checks.jsonl), and writes `out/pth.json` and the chart SVGs to `out/pth/`. Compare `out/pth.json` with [`results/pth.json`](results/pth.json): the numbers differ by however much the index has changed since 13 November 2026. Every number in the post comes from that file.

To run it on a local copy of the Parquet files instead: `python3 pth_data.py <parquet-folder> results/checks.jsonl <out-folder>`.

## Redo the download

`results/checks.jsonl` comes from `pth_check.py`, which downloads each listed project's release file again (the same file the index scanned) and saves the text of every `.pth` file in it, plus the names of any `.start` files. To redo it:

```
pip install duckdb requests
python3 -c "import duckdb; S='hf://datasets/pypi-data/py-code'; duckdb.sql(f\"COPY (SELECT project, version, file FROM '{S}/projects.parquet' WHERE project IN (SELECT project FROM '{S}/pth_files.parquet') ORDER BY project) TO 'projects.tsv' (DELIMITER '\t', HEADER false)\")"
python3 pth_check.py projects.tsv checks.jsonl --workers 8
```

Wheels are read with HTTP range requests, so only the `.pth` files are downloaded. It can be stopped and restarted; finished projects are skipped. PyPI can delete files, so a rerun may differ slightly.

## Files

| File | What it does |
|---|---|
| `pth_check.py` | Downloads each project's release file and records the path and text of every `.pth` file, and any `.start` files. |
| `pth_data.py` | Decides from each file's path whether Python runs it, sorts the running files into namespace boilerplate and the package's own code, counts projects and downloads, and draws the charts and the results card. |
| `svgchart.py` | Draws the bar charts and the card as SVG. Colours are the site's CSS variables, so the SVGs render without colour outside the site. |
| `query.sql` | The DuckDB query shown in the post. |
| `test_pth_data.py` | Tests for the path and line rules. Run with `pytest`. |
| `results/` | `checks.jsonl` (the downloaded `.pth` files), `pth.json` and the charts used in the post. |

## How the numbers were counted

- **Which projects.** Every project the py-code.org index lists in `pth_files`: those whose scanned release file has a `.pth` file with a line that starts with `import`. The index holds the latest release of every project released between 13 November 2025 and 13 November 2026, plus the 60,000 most downloaded projects.
- **Executed lines.** A line counts when it starts with `import` followed by a space or a tab, the rule Python's `site` module uses.
- **Whether it runs.** From the file's path in the wheel. At the top of the wheel, or of `<name>.data/purelib/` or `.data/platlib/`: it lands in `site-packages` and runs on every Python start. Under `<name>.data/data/`, at its root or in `lib/site-packages/`: it lands in the environment's root, which is a site directory only on Windows. Anything else, and every file in a source distribution: never.
- **What it does.** A file is namespace boilerplate when its line is the one setuptools writes for `-nspkg.pth` files (it reads `sys._getframe(1).f_locals`). Everything else counts as the package's own code. A project with both counts as running its own code.
- **Downloads.** Download counts are for the 30 days before the scan, from ClickHouse's public PyPI dataset, and exist only for the 60,000 most downloaded projects.
