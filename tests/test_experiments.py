import numpy as np
import pandas as pd
import pytest

from geopulse import experiments as ex
from geopulse import forecast as fc


def blobs(seed=0):
    rng = np.random.default_rng(seed)
    return np.vstack([rng.normal(0, 0.1, (6, 4)), rng.normal(5, 0.1, (6, 4))]), np.array([0] * 6 + [1] * 6)


def test_kmeans_and_silhouette_on_clear_clusters():
    X, truth = blobs()
    lab, inertia = ex.kmeans(X, 2)
    assert ex.adjusted_rand(lab, truth) == pytest.approx(1.0) and inertia < 1.0
    assert ex.silhouette(X, lab) > 0.9
    assert ex.silhouette(X, np.arange(12) % 2) < 0.1                         # a bad grouping scores low


def test_adjusted_rand_properties():
    a = [0, 0, 1, 1, 2, 2]
    assert ex.adjusted_rand(a, [5, 5, 7, 7, 9, 9]) == 1.0                      # label names do not matter
    assert ex.adjusted_rand(a, [0, 1, 0, 1, 0, 1]) < 0.1
    assert np.isnan(ex.adjusted_rand([1], [1]))


def rhythm_table(n_hubs=8, nodata=()):
    rows, stats = [], []
    for i in range(n_hubs):
        commuter = i < n_hubs // 2
        for dt in ("weekday", "weekend"):
            hours = np.arange(24)
            prof = np.exp(-((hours - (8 if commuter else 20)) ** 2) / 8.0) + 0.02 * (i % 3)
            share = prof / prof.sum()
            for h in hours:
                rows.append({"metric": "taxi_pickups", "hub_id": f"H{i}", "hub_name": f"Hub {i}", "day_type": dt, "hour": h,
                             "share": np.nan if i in nodata else share[h]})
        stats.append({"metric": "taxi_pickups", "hub_name": f"Hub {i}", "rhythm": "commuter" if commuter else "leisure / evening"})
    return pd.DataFrame(rows), pd.DataFrame(stats)


def test_cluster_hubs_recovers_planted_groups_and_matches_rules():
    r, s = rhythm_table()
    out, summ = ex.cluster_hubs(r, s, "taxi_pickups")
    assert summ["status"] == "ok" and summ["k"] == 2 and summ["ari_vs_rule_labels"] == 1.0
    assert summ["ari_seed_stability"] == 1.0 and len(out) == 8
    assert set(out.loc[out.rule_label == "commuter", "weekday_peak_hour"]) == {8}


def test_cluster_hubs_skips_no_data_and_tiny_inputs():
    r, s = rhythm_table(nodata=(0, 1))
    out, summ = ex.cluster_hubs(r, s, "taxi_pickups")
    assert summ["n_hubs"] == 6 and "Hub 0" not in set(out["hub_name"])
    r3, s3 = rhythm_table(n_hubs=3)
    out3, summ3 = ex.cluster_hubs(r3, s3, "taxi_pickups")
    assert out3.empty and "need at least 4" in summ3["status"]


def city_panel(days=28, rush_effect=-40.0, seed=0):
    """Rain only hurts in the morning (hand-made data, NOT real)."""
    rng = np.random.default_rng(seed)
    t = pd.date_range("2024-01-01", periods=days * 24, freq="h")
    wet = rng.random(len(t)) < 0.2
    base = 100 + 40 * np.sin(2 * np.pi * t.hour / 24)
    y = base + rush_effect * wet * ((t.hour >= 6) & (t.hour < 10)) + rng.normal(0, 2, len(t))
    df = pd.DataFrame({"datetime": t, "taxi_pickups": np.clip(y, 0, None), "is_wet": wet, "is_snow": False,
                       "temp_c": 3.0, "hour": t.hour, "day_type": np.where(t.dayofweek >= 5, "weekend", "weekday")})
    return df


def test_rain_by_daypart_finds_the_morning_effect():
    r = ex.rain_by_daypart(city_panel(), ["taxi_pickups"]).set_index("daypart")["change_pct"]
    assert r["morning (06-09)"] < -20 and abs(r["midday (10-15)"]) < 5 and abs(r["late (20-23)"]) < 5


def test_interaction_model_beats_additive_when_effect_is_local():
    ab = ex.forecast_ablation(city_panel(), "taxi_pickups").set_index("model")
    assert ab.loc["rain_by_daypart", "mae"] < ab.loc["additive_weather", "mae"] < ab.loc["hour_of_week", "mae"] + 0.5
    ab0 = ex.forecast_ablation(city_panel(rush_effect=0.0), "taxi_pickups").set_index("model")
    assert abs(ab0.loc["rain_by_daypart", "mae"] - ab0.loc["additive_weather", "mae"]) < 0.6   # no gain when there is no effect


def test_default_forecast_unchanged_by_design_hook():
    df = city_panel()
    res, _ = fc.evaluate(df, "taxi_pickups")
    lv, coef, tm = fc.fit_weather_model(df, "taxi_pickups")
    assert len(coef) == 3                                                       # wet, snow, temperature as before


def test_render_report_handles_all_cases():
    r, s = rhythm_table()
    out, summ = ex.cluster_hubs(r, s, "taxi_pickups")
    md = ex.render_report("2024-01", [summ], out, ex.rain_by_daypart(city_panel(), ["taxi_pickups"]),
                          ex.forecast_ablation(city_panel(), "taxi_pickups"))
    assert md.startswith("# Day 17") and "ARI vs rule labels" in md and "rain_by_daypart" in md and "morning (06-09)" in md
    empty = ex.render_report("2024-01", [{"metric": "m", "status": "only 2 hubs with data; need at least 4"}], pd.DataFrame(),
                             pd.DataFrame(), pd.DataFrame())
    assert "not run" in empty and "No wet hours" in empty
