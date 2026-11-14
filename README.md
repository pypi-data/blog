# py-code.org blog: code and data

The code behind the posts on the [py-code.org blog](https://py-code.org/blog/). Each post has its own folder, named after the post's URL. A folder holds the scripts that produced every number and chart in the post, plus the results they gave.

| Folder | Post |
|---|---|
| [`new-pypi-packages-imports/`](new-pypi-packages-imports/) | [What new PyPI packages are made of](https://py-code.org/blog/new-pypi-packages-imports/) |
| [`removed-stdlib-modules-pypi/`](removed-stdlib-modules-pypi/) | [PyPI code that breaks on Python 3.12 and 3.13](https://py-code.org/blog/removed-stdlib-modules-pypi/) |
| [`llm-observability-sdks-pypi/`](llm-observability-sdks-pypi/) | [The LLM observability SDKs that PyPI projects actually import](https://py-code.org/blog/llm-observability-sdks-pypi/) |
| [`ai-agent-frameworks-pypi/`](ai-agent-frameworks-pypi/) | [The AI agent frameworks that PyPI projects actually import](https://py-code.org/blog/ai-agent-frameworks-pypi/) |

## The data

The posts use the [py-code.org dataset on Hugging Face](https://huggingface.co/datasets/pypi-data/py-code): Parquet files listing the names that each PyPI project's code imports and uses. It is built by the [scanner](https://github.com/pypi-data/py-code), which reads the `.py` files of each project's latest release, parses them with Python's `ast` module without running them, and keeps the names, not the code.

The dataset is rebuilt weekly. Each post pins the dataset revision it used, so running its scripts gives the same numbers as the post.

## Running a post's scripts

You need Python 3.10 or later and [DuckDB](https://duckdb.org/):

```
pip install duckdb
cd new-pypi-packages-imports
python3 blog_data.py
```

DuckDB reads the Parquet files from Hugging Face over the network, so nothing large is downloaded first. See each folder's README for details.

## License

The code is MIT licensed. The dataset has its own terms on its Hugging Face page.
