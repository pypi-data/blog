from datetime import datetime, timezone

from october_check import first_upload


def _file(ts):
    return {"upload_time_iso_8601": ts}


def test_first_upload_picks_earliest():
    data = {"releases": {
        "2.0": [_file("2026-10-05T10:00:00.000000Z")],
        "1.0": [_file("2024-03-01T08:30:00.000000Z")],
    }}
    assert first_upload(data) == datetime(2024, 3, 1, 8, 30, tzinfo=timezone.utc)


def test_first_upload_no_files():
    assert first_upload({"releases": {"1.0": []}}) is None
    assert first_upload({}) is None


def test_estimate_created_hand_computed():
    from october_check import estimate_created

    buckets = {
        "2026-09": {"projects_in_month": 1000, "sampled": 100,
                    "first_months": {"2026-09": 40, "2026-08": 10}},
        "2026-10": {"projects_in_month": 2000, "sampled": 100,
                    "first_months": {"2026-09": 10, "2026-10": 50}},
        "2026-08": {"projects_in_month": 500, "sampled": 100,
                    "first_months": {"2026-09": 99}},  # before Sep: ignored
    }
    est, se = estimate_created(buckets, "2026-09")
    assert est == 1000 * 0.4 + 2000 * 0.1  # 600
    var = 1000**2 * 0.4 * 0.6 / 100 + 2000**2 * 0.1 * 0.9 / 100
    assert abs(se - var**0.5) < 1e-9
