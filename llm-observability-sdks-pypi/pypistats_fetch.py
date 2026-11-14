"""Fetch last-month downloads from pypistats.org for the tools' packages.

Reads the package names from out/ai-tools.json (written by ai_tools_data.py) and adds the
missing ones to results/pypistats.json. Run ai_tools_data.py again afterwards.

    python3 pypistats_fetch.py [out/ai-tools.json]
"""
import json
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path

here = Path(__file__).resolve().parent
src = Path(sys.argv[1] if len(sys.argv) > 1 else "out/ai-tools.json")
dest = here / "results" / "pypistats.json"
r = json.loads(src.read_text())
data = json.loads(dest.read_text()) if dest.exists() else {"fetched": date.today().isoformat(), "last_month": {}}
want = set()
for rows in r["tools"].values():
    for t in rows:
        want.add(t["package"])
for name in sorted(want - set(data["last_month"])):
    req = urllib.request.Request(f"https://pypistats.org/api/packages/{name.lower()}/recent",
                                 headers={"User-Agent": "py-code.org blog script"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as f:
                data["last_month"][name] = json.load(f)["data"]["last_month"]
            break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                data["last_month"][name] = None
                break
            time.sleep(10 * (attempt + 1))
    print(name, data["last_month"].get(name), flush=True)
    time.sleep(1.2)
dest.parent.mkdir(exist_ok=True)
dest.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")
