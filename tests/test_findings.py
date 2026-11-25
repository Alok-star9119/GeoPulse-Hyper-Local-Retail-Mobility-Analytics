import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from test_keynumbers import make                      # synthetic tables (hand-made, NOT real data)
from test_multimonth import MONTHS

from geopulse import catalog, findings


def test_catalog_groups_months(tmp_path):
    make(tmp_path)
    cat = catalog.build_catalog(tmp_path).set_index("table")
    assert catalog.pattern("hub_rhythm_stats_2024-01.csv") == "hub_rhythm_stats_{month}.csv"
    assert cat.loc["weather_effect_{month}.csv", "files"] == 3 and cat.loc["weather_effect_{month}.csv", "rows_total"] == 12
    assert "flag, metric, change_pct" in cat.loc["weather_effect_{month}.csv", "columns"]
    md = catalog.render(cat.reset_index())
    assert "`weather_effect_{month}.csv` | 3 | 12" in md


def test_empty_catalog(tmp_path):
    (tmp_path / "t").mkdir()
    assert catalog.build_catalog(tmp_path / "t").empty
    assert "No tables found" in catalog.render(catalog.build_catalog(tmp_path / "t"))


def test_findings_full(tmp_path):
    make(tmp_path)
    md = findings.build(tmp_path, MONTHS)
    assert md.startswith("# Findings Draft") and "Months analysed: 2024-01, 2024-02, 2024-03 (91 days)" in md
    assert "busiest hub is Hub H10" in md                                      # H10 has the largest planted volume
    assert "No data (no station or zone" in md and "Hub H01" in md             # two bike hubs have no data
    assert "1 of 3 retail-mobility rank correlations" in md and "poi_per_km2 vs taxi_total" in md
    assert "is_wet, bike_starts_hubs: -31.0% on average" in md
    assert "6.5% (with weather)" in md and "weather changes WAPE by +1.5 points" in md
    assert "Checks run: 15 across 3 month(s): 11 pass, 3 warn, 1 fail" in md
    assert "Months with failed checks" in md and "2024-03" in md
    assert "cause" in md.lower() and "Limitations" in md


def test_findings_single_month_and_empty(tmp_path):
    make(tmp_path, MONTHS[:1])
    md = findings.build(tmp_path, MONTHS[:1])
    assert "rho = " in md and "retail-mobility rank correlations kept" not in md       # no consistency claim from one month
    empty = findings.build(tmp_path / "x", [])
    assert "No processed months" in empty and "No hub rhythm tables" in empty and "No forecast tables" in empty
