import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent))
from test_multimonth import MONTHS, write_month          # synthetic tables (hand-made, not real data)

from geopulse import dashboard as db


def add_rhythm(tables, ym):
    rows = []
    for metric in ("taxi_pickups", "bike_starts"):
        for h in ("Hub H01", "Hub H02"):
            for hour in range(24):
                rows.append({"metric": metric, "hub_id": h[-3:], "hub_name": h, "day_type": "weekday", "hour": hour,
                             "avg": float(hour + 1) if h == "Hub H01" else np.nan, "share": 0.04})
    pd.DataFrame(rows).to_csv(tables / f"hub_hourly_rhythm_{ym}.csv", index=False)


@pytest.fixture(scope="module")
def tables(tmp_path_factory):
    t = tmp_path_factory.mktemp("t")
    for i, ym in enumerate(MONTHS):
        write_month(t, ym, i)
        add_rhythm(t, ym)
    return t


def test_full_page(tables):
    html = db.render(MONTHS, tables)
    assert html.startswith("<!doctype html>") and html.count("<svg") >= 4
    assert "2024-01 to 2024-03" in html and "Hub H03" in html and "no data" in html      # no-data bike hubs labelled
    assert "http://" not in html and "https://" not in html and "<script" not in html    # offline, no libraries
    assert "Taxi pickups per day" in html and "poi_per_km2" in html


def test_kpis_use_totals(tables):
    ov = db.mm.monthly_overview(tables, MONTHS)
    html = db.kpi_cards(ov)
    assert f"{int(ov['taxi_total'].sum()):,}" in html


def test_html_is_escaped():
    out = db.svg_bars(["<script>x</script>"], [1.0], "t<b>")
    assert "<script>" not in out and "&lt;script&gt;" in out
    assert "<script>" not in db.table(["h"], [["<img onerror=1>"]])


def test_lines_break_on_nan_and_handle_empty():
    s = db.svg_lines({"a": [1.0, np.nan, 3.0, 4.0]}, list("abcd"), "x")
    assert len(re.findall(r"M", re.search(r"d='([^']*)'", s).group(1))) == 2           # line broken at the NaN
    assert "no data" in db.svg_lines({"a": [np.nan]}, ["a"], "x")
    assert "no data" in db.svg_bars(["a"], [np.nan], "x")


def test_missing_tables_do_not_crash(tmp_path):
    html = db.render(["2024-01"], tmp_path)
    assert "No processed months found" in html
    pd.DataFrame({"datetime": pd.date_range("2024-01-01", periods=744, freq="h"), "taxi_pickups": 1,
                  "bike_starts_hubs": 1, "temp_c": 1.0, "precip_mm": 0.0}).to_csv(tmp_path / "city_hourly_panel_2024-01.csv", index=False)
    html = db.render(["2024-01"], tmp_path)
    assert "Not available for these months" in html and "Month by month" not in html     # one month: no comparison chart


def test_script_writes_file(tables, tmp_path):
    import subprocess
    out = tmp_path / "d.html"
    root = Path(__file__).parent.parent
    r = subprocess.run([sys.executable, str(root / "scripts" / "build_dashboard.py"), "--tables-dir", str(tables), "--out", str(out)],
                       capture_output=True, text=True, env={"PYTHONPATH": str(root / "src"), "PATH": "/usr/bin:/bin"})
    assert r.returncode == 0, r.stderr
    assert out.read_text().startswith("<!doctype html>")
