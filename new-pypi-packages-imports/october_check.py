"""Check whether October 2026 really has more brand-new PyPI projects.

The index keeps only each project's latest release, so the count of projects
whose latest release falls in a month is not the count of new projects. For a
sample of projects per month, ask PyPI for the full release history and count
those whose first upload falls in that month.

Usage: october_check.py [<projects.parquet>] [<out.json>] [--sample 300]

With no arguments it reads the pinned 13 November 2026 snapshot from Hugging Face
and writes october_check.json. It asks PyPI about each sampled project, one
request every 0.2 s, so 300 per month takes a few minutes.
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

MONTHS = ["2026-08", "2026-09", "2026-10"]
BUCKETS = MONTHS + ["2026-11"]
PARTIAL = "2026-11"  # snapshot ends 2026-11-13
USER_AGENT = "py-code-blog-check"
DELAY = 0.2
# October is "real" only if created(Oct) exceeds this multiple of created(Sep).
CLEAR_FACTOR = 1.25


def first_upload(pypi_json):
    """Earliest upload_time_iso_8601 over all files of all releases, or None."""
    times = []
    for files in (pypi_json.get("releases") or {}).values():
        for f in files or []:
            ts = f.get("upload_time_iso_8601")
            if ts:
                times.append(datetime.fromisoformat(ts.replace("Z", "+00:00")))
    return min(times) if times else None


def fetch_json(name):
    req = urllib.request.Request(
        f"https://pypi.org/pypi/{name}/json", headers={"User-Agent": USER_AGENT}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def sample_projects(parquet, month, n):
    import duckdb

    con = duckdb.connect()
    total = con.execute(
        "SELECT count(*) FROM read_parquet(?) WHERE strftime(upload_time, '%Y-%m') = ?",
        [parquet, month],
    ).fetchone()[0]
    rows = con.execute(
        "SELECT project FROM read_parquet(?) WHERE strftime(upload_time, '%Y-%m') = ? "
        "ORDER BY hash(project) LIMIT ?",
        [parquet, month, n],
    ).fetchall()
    return total, [r[0] for r in rows]


def estimate_created(buckets, month):
    """Estimate how many projects were created in `month`.

    A project created in M has its latest release in M or later, so sum over
    buckets B >= M: projects_in_bucket(B) * share of B's sample first uploaded
    in M. `buckets` maps "YYYY-MM" to {"projects_in_month", "sampled",
    "first_months": {month: count}}. Returns (estimate, standard error), with
    the buckets treated as independent binomials.
    """
    est, var = 0.0, 0.0
    for b, d in buckets.items():
        if b < month or not d["sampled"]:
            continue
        n, total = d["sampled"], d["projects_in_month"]
        p = d["first_months"].get(month, 0) / n
        est += total * p
        var += total * total * p * (1 - p) / n
    return est, var ** 0.5


def decide(created):
    """created: {month: (estimate, se)} for 2026-09 and 2026-10."""
    sep, sep_se = created["2026-09"]
    octo, oct_se = created["2026-10"]
    bands_clear = octo - 2 * oct_se > sep + 2 * sep_se
    verdict = "real" if octo > CLEAR_FACTOR * sep and bands_clear else "artifact"
    parts = ", ".join(
        f"{m}: {created[m][0]:.0f} (+/-{2 * created[m][1]:.0f})" for m in MONTHS
    )
    reason = (
        f"Estimated projects created per month (+/- 2 SE): {parts}. "
        f"Rule: real if October is more than {CLEAR_FACTOR}x September and the "
        f"bands do not overlap."
    )
    return verdict, reason

HF_PROJECTS = ("hf://datasets/pypi-data/py-code@9d81d70d6519d77f4dee4811b3e3a5d88379c17d"
               "/projects.parquet")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("parquet", nargs="?", default=HF_PROJECTS)
    ap.add_argument("out", nargs="?", default="october_check.json")
    ap.add_argument("--sample", type=int, default=300)
    args = ap.parse_args()

    buckets, new_sample = {}, {m: [] for m in MONTHS}
    for bucket in BUCKETS:
        total, names = sample_projects(args.parquet, bucket, args.sample)
        first_months, skipped = {}, 0
        for name in names:
            time.sleep(DELAY)
            try:
                first = first_upload(fetch_json(name))
            except (urllib.error.URLError, OSError, ValueError) as e:
                skipped += 1
                print(f"skip {name}: {e}", file=sys.stderr)
                continue
            if first is None:
                skipped += 1
                continue
            fm = first.astimezone(timezone.utc).strftime("%Y-%m")
            first_months[fm] = first_months.get(fm, 0) + 1
            if fm in new_sample:
                new_sample[fm].append(name)
        buckets[bucket] = {
            "projects_in_month": total,
            "sampled": len(names) - skipped,
            "skipped": skipped,
            "partial": bucket == PARTIAL,
            "first_months": dict(sorted(first_months.items())),
        }
        print(bucket, buckets[bucket]["sampled"], file=sys.stderr)
    created = {m: estimate_created(buckets, m) for m in MONTHS}
    result = {
        "buckets": buckets,
        "created": {
            m: {"estimate": round(e), "se": round(se, 1), "band_low": round(e - 2 * se),
                "band_high": round(e + 2 * se), "new_sample": new_sample[m]}
            for m, (e, se) in created.items()
        },
    }
    result["verdict"], result["reason"] = decide(created)
    with open(args.out, "w") as f:
        json.dump(result, f, indent=2)
    print(result["verdict"], result["reason"])


if __name__ == "__main__":
    main()
