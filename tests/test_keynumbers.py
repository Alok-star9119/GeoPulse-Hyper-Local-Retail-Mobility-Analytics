import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from test_multimonth import MONTHS, write_month          # synthetic tables (hand-made, not real data)

from geopulse import keynumbers as kn


def add_extra(t, ym, bad=0):
    pd.DataFrame({"check": list("abcde"), "scope": "c", "status": ["pass"] * (4 - bad) + ["warn"] + ["fail"] * bad}).to_csv(
        t / f"quality_checks_{ym}.csv", index=False)
    pd.DataFrame({"target": ["taxi_pickups"] * 3, "model": ["seasonal_naive", "hour_of_week", "hour_of_week_weather"],
                  "wape_pct": [9.0, 8.0, 6.5]}).to_csv(t / f"forecast_metrics_{ym}.csv", index=False)


def make(tmp_path, months=MONTHS):
    for i, ym in enumerate(months):
        write_month(tmp_path, ym, i)
        add_extra(tmp_path, ym, bad=1 if i == 2 else 0)
    return tmp_path


def test_quality_and_forecast_summaries(tmp_path):
    t = make(tmp_path)
    q = kn.quality_summary(t, MONTHS).set_index("month")
    assert q.loc["2024-01", "pass"] == 4 and q.loc["2024-01", "warn"] == 1 and q.loc["2024-03", "fail"] == 1
    f = kn.forecast_summary(t, MONTHS)
    assert len(f) == 3 and (f["weather_gain_pts"] == 1.5).all()
    assert kn.quality_summary(t, ["2099-01"]).empty and kn.forecast_summary(t, ["2099-01"]).empty


def test_stability_counts(tmp_path):
    s = kn.stability_summary(make(tmp_path), MONTHS)
    assert s["labels_total"] == 18 and s["labels_stable"] == 17                  # the planted H03 change
    assert s["corr_total"] == 3 and s["corr_consistent"] == 1
    assert kn.stability_summary(tmp_path, MONTHS[:1]) == {}


def test_render_full_and_empty(tmp_path):
    t = make(tmp_path)
    md = kn.render(MONTHS, kn.quality_summary(t, MONTHS), kn.forecast_summary(t, MONTHS), kn.stability_summary(t, MONTHS), tmp_path)
    assert "| 2024-03 | 5 | 3 | 1 | 1 |" in md and "17 of 18" in md and "1 of 3" in md
    assert "none of the generated reports" in md
    empty = kn.render([], pd.DataFrame(), pd.DataFrame(), {}, tmp_path)
    assert "No quality tables" in empty and "No forecast tables" in empty and "Needs at least 2 months" in empty
    (tmp_path / "reports").mkdir()
    (tmp_path / "reports/dashboard.html").write_text("x")
    assert "`reports/dashboard.html`" in kn.render(MONTHS, pd.DataFrame(), pd.DataFrame(), {}, tmp_path)
