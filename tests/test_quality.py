import numpy as np
import pandas as pd
import pytest

from geopulse import ingest_weather as w
from geopulse import panel as p
from geopulse import quality as q
from geopulse.sources import get_hubs, load_catalog


def make_weather():
    times = pd.date_range("2024-01-01", periods=744, freq="h")
    return w.add_weather_flags(w.parse_hourly({"hourly": {
        "time": [t.strftime("%Y-%m-%dT%H:%M") for t in times],
        "temperature_2m": [1.0] * 744, "precipitation": [0.5 if t.day == 5 else 0.0 for t in times],
        "rain": [0.0] * 744, "snowfall": [0.0] * 744, "wind_speed_10m": [10.0] * 744,
        "weather_code": [3] * 744}}))


@pytest.fixture
def good():
    """Healthy synthetic panels (hand-made, NOT real data)."""
    rng = np.random.default_rng(0)
    grid = p.hour_grid(2024, 1)
    base = 50 + 30 * np.sin((grid.hour.values - 6) / 24 * 2 * np.pi)
    taxi = pd.DataFrame({"datetime": grid, "taxi_pickups": (base * 10 + rng.integers(0, 5, len(grid))).astype(int)})
    # bikes in two hubs
    rows = []
    for hid in ("H01", "H02"):
        for t, b in zip(grid, base):
            rows.append({"hub_id": hid, "datetime": t, "bike_starts": int(b / 5) + 3})
    bike = pd.DataFrame(rows)
    weather = make_weather()
    city = p.city_panel(taxi, bike, weather, 2024, 1)
    hub = p.hub_panel(bike, weather, get_hubs(), 2024, 1)
    return city, hub


def status(results, check, scope=None):
    r = results[results.check == check]
    if scope:
        r = r[r.scope == scope]
    return list(r.status)


def test_good_data_has_no_failures(good):
    city, hub = good
    res, _ = q.run_all(city, hub, 2024, 1)
    assert "fail" not in set(res.status), res[res.status == "fail"]
    assert status(res, "hub_sum_equals_city") == ["pass"]
    assert status(res, "row_count", "hub panel") == ["pass"]


def test_missing_column_fails(good):
    city, hub = good
    assert q.check_schema(city.drop(columns=["temp_c"]), q.CITY_REQUIRED, "city")["status"] == "fail"


def test_wrong_row_count_and_duplicate(good):
    city, _ = good
    dup = pd.concat([city, city.iloc[[0]]], ignore_index=True)
    assert q.check_row_count(dup, 744, "c")["status"] == "fail"
    assert q.check_unique(dup, ["datetime"], "c")["status"] == "fail"
    assert q.check_unique(city, ["datetime"], "c")["status"] == "pass"


def test_negative_and_null_detected(good):
    city, _ = good
    bad = city.copy()
    bad.loc[3, "taxi_pickups"] = -5
    bad.loc[4, "temp_c"] = np.nan
    assert q.check_no_negative(bad, ["taxi_pickups"], "c")["status"] == "fail"
    assert q.check_nulls(bad, ["temp_c"], "c")["status"] == "fail"


def test_weather_range_detected(good):
    city, _ = good
    bad = city.copy()
    bad.loc[0, "temp_c"] = 99
    assert q.check_weather_ranges(bad, "c")["status"] == "fail"
    assert q.check_weather_ranges(city, "c")["status"] == "pass"


def test_daytime_gap_warns(good):
    city, _ = good
    bad = city.copy()
    idx = bad.index[(bad.hour == 12)][0]
    bad.loc[idx, "taxi_pickups"] = 0
    assert q.check_daytime_gaps(bad, ["taxi_pickups"], "c")["status"] == "warn"
    assert q.check_daytime_gaps(city, ["taxi_pickups"], "c")["status"] == "pass"


def test_hub_city_mismatch_detected(good):
    city, hub = good
    bad = hub.copy()
    bad.loc[bad.index[10], "bike_starts"] += 7
    assert q.check_hub_matches_city(bad, city)["status"] == "fail"


def test_static_columns_skip_and_vary(good):
    _, hub = good
    assert q.check_static_columns(hub, ["osm_poi_total"])["status"] == "skip"
    h2 = hub.copy()
    h2["osm_poi_total"] = 10
    assert q.check_static_columns(h2, ["osm_poi_total"])["status"] == "pass"
    h2.loc[h2.index[0], "osm_poi_total"] = 11
    assert q.check_static_columns(h2, ["osm_poi_total"])["status"] == "fail"


def test_hubs_without_bikes_warns(good):
    _, hub = good
    r = q.check_hubs_without_bikes(hub)
    assert r["status"] == "warn" and "Harlem" in r["detail"]   # only H01/H02 have bikes in the fixture


def test_outlier_injected_spike_is_found(good):
    city, _ = good
    spiked = city.copy()
    i = spiked.index[(spiked.hour == 10) & (spiked.day_type == "weekday")][3]
    spiked.loc[i, "taxi_pickups"] *= 20
    out = q.flag_outliers(spiked, "taxi_pickups")
    assert spiked.loc[i, "datetime"] in set(out["datetime"])
    res, anomalies = q.check_outliers(spiked, ["taxi_pickups", "bike_starts_hubs"])
    assert len(anomalies) >= 1 and res["scope"] == "city panel"


def test_removed_share_thresholds():
    f = q.check_removed_share
    assert f({"rows": 1000, "rows_after_clean": 950}, "t", "rows", "rows_after_clean")["status"] == "pass"
    assert f({"rows": 1000, "rows_after_clean": 850}, "t", "rows", "rows_after_clean")["status"] == "warn"
    assert f({"rows": 1000, "rows_after_clean": 500}, "t", "rows", "rows_after_clean")["status"] == "fail"
    assert f(None, "t", "rows", "rows_after_clean")["status"] == "skip"


def test_catalog_check():
    cat = load_catalog()
    assert q.check_catalog_verified(cat)["status"] == "warn"      # repo catalog starts 'unverified'
    cat.loc[cat.source_id.isin(q.SOURCES_USED), "status"] = "verified"
    assert q.check_catalog_verified(cat)["status"] == "pass"


def test_render_report(good):
    city, hub = good
    res, an = q.run_all(city, hub, 2024, 1)
    lineage = pd.DataFrame({"file": ["city_hourly_panel_2024-01.csv"], "rows": [744]})
    md = q.render_report(res, an, lineage, "2024-01")
    assert md.startswith("# Week 1 Data Quality Report (2024-01)")
    assert "| PASS |" in md and "city_hourly_panel_2024-01.csv" in md and "## Decisions" in md
