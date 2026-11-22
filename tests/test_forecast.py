import numpy as np
import pandas as pd
import pytest

from geopulse import forecast as fc


def synth(days=28, seed=0, wet_effect=-30.0, noise=2.0):
    """Hand-made hourly data: weekly pattern + rain effect + noise (NOT real data)."""
    rng = np.random.default_rng(seed)
    t = pd.date_range("2024-01-01", periods=days * 24, freq="h")
    pattern = 100 + 50 * np.sin(2 * np.pi * (t.hour / 24)) + 20 * (t.dayofweek >= 5)
    wet = rng.random(len(t)) < 0.15
    y = pattern + wet_effect * wet + rng.normal(0, noise, len(t))
    return pd.DataFrame({"datetime": t, "taxi_pickups": np.clip(y, 0, None), "is_wet": wet,
                         "is_snow": False, "temp_c": 2.0 + rng.normal(0, 1, len(t))})


def test_split_is_time_ordered_and_sized():
    df = synth()
    tr, te = fc.split_by_days(df, 7)
    assert len(te) == 7 * 24 and tr["datetime"].max() < te["datetime"].min()
    with pytest.raises(ValueError):
        fc.split_by_days(synth(days=16), 7)                      # only 9 training days


def test_hour_of_week_mean_recovers_pattern():
    df = synth(noise=0.0, wet_effect=0.0)
    hm = fc.hour_of_week_mean(df, "taxi_pickups")
    assert len(hm) == 168 and hm.loc[0] == pytest.approx(df["taxi_pickups"].iloc[0])


def test_weather_model_beats_plain_hour_of_week_when_rain_matters():
    res, preds = fc.evaluate(synth(), "taxi_pickups")
    r = res.set_index("model")
    assert r.loc["hour_of_week_weather", "mae"] < r.loc["hour_of_week", "mae"]
    assert r.loc["hour_of_week_weather", "wape_pct"] < r.loc["seasonal_naive", "wape_pct"]
    assert res["wet_effect"].iloc[0] == pytest.approx(-30, abs=4)         # recovers the planted rain effect
    assert len(preds) == 7 * 24 and preds["hour_of_week_weather"].min() >= 0


def test_weather_model_no_better_when_weather_irrelevant():
    res, _ = fc.evaluate(synth(wet_effect=0.0), "taxi_pickups")
    r = res.set_index("model")
    assert abs(r.loc["hour_of_week_weather", "mae"] - r.loc["hour_of_week", "mae"]) < 0.5
    assert abs(res["wet_effect"].iloc[0]) < 2


def test_no_leak_naive_uses_earlier_values():
    df = synth(noise=0.0, wet_effect=0.0)
    _, te = fc.split_by_days(df)
    pred = fc.seasonal_naive(df, te, "taxi_pickups")
    assert not np.isnan(pred).any() and np.allclose(pred, te["taxi_pickups"])     # exact weekly repeat


def test_never_wet_in_training_does_not_crash():
    df = synth(wet_effect=0.0)
    df["is_wet"] = False
    res, _ = fc.evaluate(df, "taxi_pickups")
    assert res["wet_effect"].iloc[0] == 0.0


def test_metrics_edge_cases():
    m = fc.metrics([10, 20, np.nan], [12, 18, 5])
    assert m["n"] == 2 and m["mae"] == 2.0 and m["wape_pct"] == pytest.approx(13.3) and m["bias_pct"] == 0.0
    z = fc.metrics([0, 0], [1, 1])
    assert z["n"] == 2 and np.isnan(z["wape_pct"])                         # no demand: percentage error undefined
    assert fc.metrics([], [])["n"] == 0


def test_hub_evaluation_marks_no_data():
    a, b = synth(), synth(seed=1)
    a["hub_id"], a["hub_name"] = "H1", "Hub 1"
    b["hub_id"], b["hub_name"] = "H2", "Hub 2"
    b["taxi_pickups"] = 0.0
    out = fc.hub_evaluation(pd.concat([a, b]), "taxi_pickups").set_index("hub_id")
    assert out.loc["H2", "status"] == "no data" and pd.isna(out.loc["H2"].get("wape_how"))
    assert out.loc["H1", "status"] == "ok" and out.loc["H1", "weather_gain_pts"] > 0


def test_render_report():
    res, _ = fc.evaluate(synth(), "taxi_pickups")
    a, b = synth(), synth(seed=1)
    a["hub_id"], a["hub_name"] = "H1", "Hub 1"
    b["hub_id"], b["hub_name"], b["taxi_pickups"] = "H2", "Hub 2", 0.0
    md = fc.render_report("2024-01", res, fc.hub_evaluation(pd.concat([a, b]), "taxi_pickups"))
    assert md.startswith("# Day 13") and "hour_of_week_weather" in md and "Hub 1" in md
    assert "No data (not forecast): Hub 2 (taxi_pickups)" in md
