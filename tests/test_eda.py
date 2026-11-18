import numpy as np
import pandas as pd
import pytest

from geopulse import eda


def make_hub_panel():
    """Synthetic hubs with known rhythms (hand-made, NOT real data), January 2024 grid."""
    grid = pd.date_range("2024-01-01", periods=31 * 24, freq="h")
    rows = []
    for t in grid:
        h, weekend = t.hour, t.dayofweek >= 5
        commuter = 100 if h in (7, 8, 9, 17, 18, 19) else 5
        if weekend:
            commuter *= 0.4
        leisure = 100 if h in (20, 21, 22, 23) else 8
        if weekend:
            leisure *= 1.5
        midday = 100 if h in (11, 12, 13, 14) else 6
        flat = 20
        for hid, name, typ, v in (("A", "Commuter Hub", "office", commuter), ("B", "Leisure Hub", "tourist", leisure),
                                  ("C", "Midday Hub", "shopping", midday), ("D", "Flat Hub", "mixed", flat),
                                  ("E", "Empty Hub", "none", 0)):
            rows.append({"hub_id": hid, "hub_name": name, "hub_type": typ, "datetime": t,
                         "date": t.date(), "hour": h, "day_of_week": t.dayofweek,
                         "day_type": "weekend" if weekend else "weekday",
                         "bike_starts": int(v), "taxi_pickups": int(v * 2)})
    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def hub():
    return make_hub_panel()


def test_hourly_rhythm_shares_sum_to_one(hub):
    r = eda.hourly_rhythm(hub, "bike_starts")
    sums = r.groupby(["hub_id", "day_type"])["share"].sum()
    assert sums[("A", "weekday")] == pytest.approx(1.0, abs=0.01)
    assert sums[("D", "weekend")] == pytest.approx(1.0, abs=0.01)
    assert r[(r.hub_id == "E")]["share"].isna().all()           # empty hub has no shape


def test_weekly_heatmap_shape_and_values(hub):
    h = eda.weekly_heatmap(hub[hub.hub_id == "A"], "bike_starts")
    assert h.shape == (7, 24) and list(h.index[:2]) == ["Mon", "Tue"]
    assert h.loc["Mon", 8] == 100 and h.loc["Sat", 8] == 40       # weekend commuter volume is 40%


def test_weekend_ratio(hub):
    assert eda.weekend_ratio(hub[hub.hub_id == "D"], "bike_starts") == pytest.approx(1.0)
    assert eda.weekend_ratio(hub[hub.hub_id == "A"], "bike_starts") < 0.6
    assert eda.weekend_ratio(hub[hub.hub_id == "B"], "bike_starts") > 1.2
    assert np.isnan(eda.weekend_ratio(hub[hub.hub_id == "E"], "bike_starts"))


def test_daypart_shares_add_up():
    prof = pd.Series(np.ones(24), index=range(24))
    s = eda.daypart_shares(prof)
    assert sum(s.values()) == pytest.approx(1.0)
    assert s["night (0-5)"] == pytest.approx(6 / 24)


def test_labels_recover_known_rhythms(hub):
    st = eda.hub_rhythm_stats(hub, "bike_starts").set_index("hub_id")
    assert st.loc["A", "rhythm"] == "commuter"
    assert st.loc["B", "rhythm"] == "leisure / evening"
    assert st.loc["C", "rhythm"] == "midday / shopping"
    assert st.loc["D", "rhythm"] == "all-day mixed"
    assert st.loc["E", "rhythm"] == "no data" and st.loc["E", "total"] == 0
    assert st.loc["A", "weekday_peak_hour"] in (7, 8, 9, 17, 18, 19)
    assert st.loc["D", "peak_to_mean"] == pytest.approx(1.0)
    assert st.loc["B", "weekend_peak_hour"] in (20, 21, 22, 23)


def test_classify_edge_cases():
    assert eda.classify_rhythm(np.nan, 0.1, 0.1, 1.0) == "no data"
    assert eda.classify_rhythm(0.35, 0.1, 0.1, np.nan) == "commuter"      # unknown weekend ratio does not block commuter
    # rush share is high, but weekends are busier (ratio 1.2 is not < 0.9), so it is not a commuter hub
    assert eda.classify_rhythm(0.35, 0.25, 0.1, 1.2) == "leisure / evening"


def test_profile_similarity_is_symmetric_with_unit_diagonal(hub):
    r = eda.hourly_rhythm(hub[hub.hub_id.isin(["A", "B", "C"])], "bike_starts")
    sim = eda.profile_similarity(r)
    assert sim.shape == (3, 3)
    assert np.allclose(np.diag(sim.values), 1.0) and np.allclose(sim.values, sim.values.T)
    assert sim.loc["Commuter Hub", "Leisure Hub"] < 0.5


def test_flat_profile_has_undefined_similarity(hub):
    # a perfectly flat hub has zero variance, so its correlation with others is undefined (NaN)
    r = eda.hourly_rhythm(hub[hub.hub_id.isin(["A", "D"])], "bike_starts")
    sim = eda.profile_similarity(r)
    assert np.isnan(sim.loc["Flat Hub", "Commuter Hub"])


def test_daily_extremes():
    grid = pd.date_range("2024-01-01", periods=10 * 24, freq="h")
    city = pd.DataFrame({"datetime": grid, "date": grid.date, "day_of_week": grid.dayofweek,
                         "taxi_pickups": 10, "precip_mm": 0.0, "temp_c": 1.0})
    city.loc[city.date == pd.Timestamp("2024-01-04").date(), "taxi_pickups"] = 1      # storm day
    city.loc[city.date == pd.Timestamp("2024-01-04").date(), "precip_mm"] = 2.0
    e = eda.daily_extremes(city, "taxi_pickups", k=2)
    quiet = e[e.kind == "quietest"].iloc[0]
    assert str(quiet["date"]) == "2024-01-04" and quiet["weekday"] == "Thu" and quiet["precip_mm"] == 48.0
    assert len(e) == 4


def test_render_report_contains_sections(hub):
    stats = pd.concat([eda.hub_rhythm_stats(hub, m) for m in ("taxi_pickups", "bike_starts")], ignore_index=True)
    city = hub.groupby(["datetime", "date", "hour", "day_of_week"], as_index=False)[["taxi_pickups", "bike_starts"]].sum()
    city["precip_mm"], city["temp_c"] = 0.0, 1.0
    ext = pd.concat([eda.daily_extremes(city, m) for m in ("taxi_pickups", "bike_starts")], ignore_index=True)
    md = eda.render_report(stats, ext, "2024-01")
    assert md.startswith("# Day 9: Hub Rhythm EDA (2024-01)")
    assert "| Commuter Hub |" in md and "commuter" in md and "no data" in md
    assert "## Busiest and quietest days" in md and "Taxi Pickups by hub" in md
