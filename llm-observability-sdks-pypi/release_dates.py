"""Fetch each tool package's first upload date on PyPI into results/first_release.json.

    python3 release_dates.py
"""
import json
import urllib.request
from pathlib import Path

from ai_tools_data import GROUPS

here = Path(__file__).resolve().parent
dest = here / "results" / "first_release.json"
# LlamaIndex's downloads are counted for llama-index-core (2024), but the project's first
# package was llama-index, so the posts date it from that.
out = {}
packages = [spec[0] for specs in GROUPS.values() for spec in specs.values()] + ["llama-index"]
for pkg in packages:
    req = urllib.request.Request(f"https://pypi.org/pypi/{pkg}/json",
                                 headers={"User-Agent": "py-code.org blog script"})
    try:
        with urllib.request.urlopen(req, timeout=30) as f:
            rel = json.load(f)["releases"]
    except urllib.error.HTTPError:
        out[pkg] = None
        continue
    times = [u["upload_time"] for files in rel.values() for u in files]
    out[pkg] = min(times)[:10] if times else None
    print(pkg, out[pkg])
dest.parent.mkdir(exist_ok=True)
dest.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
