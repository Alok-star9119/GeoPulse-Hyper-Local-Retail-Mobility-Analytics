import numpy as np
import pandas as pd
import pytest

from geopulse import multimonth as mm

MONTHS = ["2024-01", "2024-02", "2024-03"]
HUBS = [f"H{i:02d}" for i in range(1, 11)]
BASE = {h: (i + 1) * 1000 for i, h in enumerate(HUBS)}               # hub volume rank is fixed by construction


def write_month(tables, ym, idx):
    """Synthetic per-month tables with planted structure (hand-made, NOT real data)."""
    rng = np.random.default_rng(idx)
    stats = []
    for metric in ("taxi_pickups", "bike_starts"):
        for i, h in enumerate(HUBS):
            label = "commuter" if i < 5 else "leisure / evening"
            if metric == "taxi_pickups" and h == "H03" and ym == "2024-03":
                label = "all-day mixed"                                # one planted label change
            total = int(BASE[h] * (1 + 0.05 * rng.standard_normal())) if not (metric == "bike_starts" and i < 2) else 0
            stats.append({"metric": metric, "hub_id": h, "hub_name": f"Hub {h}", "total": total,
                          "weekday_peak_hour": 8 + (i % 3), "weekend_ratio": 0.8 + 0.02 * i,
                          "rhythm": label if total > 0 else "no data"})
    pd.DataFrame(stats).to_csv(tables / f"hub_rhythm_stats_{ym}.csv", index=False)
    pd.DataFrame([
        {"retail_feature": "poi_per_km2", "mobility_feature": "taxi_total", "n_hubs": 10, "rho": [0.8, 0.75, 0.7][idx]},
        {"retail_feature": "diversity", "mobility_feature": "bike_total", "n_hubs": 8, "rho": [0.5, -0.4, 0.3][idx]},   # flips sign
        {"retail_feature": "share_fashion", "mobility_feature": "taxi_rush_share", "n_hubs": 10, "rho": [0.5, 0.1, 0.4][idx]},  # too weak once
        {"retail_feature": "share_services", "mobility_feature": "bike_total", "n_hubs": 8, "rho": np.nan},
    ]).to_csv(tables / f"retail_mobility_correlations_{ym}.csv", index=False)
    cold = [-3.0, -4.0, -2.0][idx]
    pd.DataFrame([
        {"flag": "is_wet", "metric": "taxi_pickups", "change_pct": [-5.0, -6.0, -4.0][idx]},
        {"flag": "is_wet", "metric": "bike_starts_hubs", "change_pct": [-30.0, -28.0, -35.0][idx]},
        {"flag": "is_cold", "metric": "taxi_pickups", "change_pct": [-2.0, -2.0, -9.0][idx]},
        {"flag": "is_cold", "metric": "bike_starts_hubs", "change_pct": [-8.0, -9.0, -1.0][idx]},   # flips in March
    ]).to_csv(tables / f"weather_effect_{ym}.csv", index=False)
    grid = pd.date_range(f"{ym}-01", periods=pd.Period(ym).days_in_month * 24, freq="h")
    pd.DataFrame({"datetime": grid, "taxi_pickups": 100, "bike_starts_hubs": 10 + 5 * idx,
                  "temp_c": cold, "precip_mm": np.where(grid.hour == 9, 0.5, 0.0)}).to_csv(
        tables / f"city_hourly_panel_{ym}.csv", index=False)


@pytest.fixture(scope="module")
def tables(tmp_path_factory):
    t = tmp_path_factory.mktemp("tables")
    for i, ym in enumerate(MONTHS):
        write_month(t, ym, i)
    return t


def test_discover_and_stack(tables):
    assert mm.discover_months(tables) == MONTHS
    assert mm.discover_months(tables, "weather_effect_{ym}.csv") == MONTHS
    s, found = mm.stack(tables, "hub_rhythm_stats_{ym}.csv", MONTHS + ["2099-01"])
    assert found == MONTHS and set(s["month"]) == set(MONTHS) and len(s) == 60
    empty, none = mm.stack(tables, "hub_rhythm_stats_{ym}.csv", ["2099-01"])
    assert empty.empty and none == []


def test_monthly_overview(tables):
    o = mm.monthly_overview(tables, MONTHS).set_index("month")
    assert o.loc["2024-02", "days"] == 29                                  # leap year
    assert o.loc["2024-01", "taxi_per_day"] == 2400 and o.loc["2024-03", "bike_per_day"] == 20 * 24
    assert o.loc["2024-01", "wet_hours"] == 31 and o.loc["2024-02", "freezing_hours"] == 29 * 24
    assert o.loc["2024-02", "temp_mean_c"] == -4.0


def test_label_stability_finds_planted_change(tables):
    s, _ = mm.stack(tables, "hub_rhythm_stats_{ym}.csv", MONTHS)
    lab = mm.label_stability(s)
    changed = lab[~lab.stable]
    assert len(changed) == 1 and changed.iloc[0]["hub_id"] == "H03" and changed.iloc[0]["metric"] == "taxi_pickups"
    assert "2024-03=all-day mixed" in changed.iloc[0]["labels_by_month"]
    bike = lab[lab.metric == "bike_starts"]
    assert len(bike) == 8 and (bike.n_months == 3).all()                   # two no-data hubs ignored in every month


def test_rank_stability_high_when_order_is_fixed(tables):
    s, _ = mm.stack(tables, "hub_rhythm_stats_{ym}.csv", MONTHS)
    r = mm.rank_stability(s)
    assert len(r) == 2 * 3                                                 # 2 metrics x 3 month pairs
    assert (r["rho"] > 0.9).all() and (r["top3_overlap"] == 3).all()
    bike = r[r.metric == "bike_starts"]
    assert (bike.n_hubs == 8).all()                                        # zeros treated as no data, not as rank 0


def test_rank_stability_detects_reshuffle():
    rows = []
    for m, order in (("2024-01", range(10)), ("2024-02", reversed(range(10)))):
        for h, v in zip([f"Hub {i}" for i in range(10)], order):
            rows.append({"metric": "taxi_pickups", "hub_name": h, "month": m, "total": (v + 1) * 100})
    r = mm.rank_stability(pd.DataFrame(rows))
    assert r.iloc[0]["rho"] == pytest.approx(-1.0) and r.iloc[0]["top3_overlap"] == 0


def test_correlation_consistency(tables):
    c, _ = mm.stack(tables, "retail_mobility_correlations_{ym}.csv", MONTHS)
    t = mm.correlation_consistency(c).set_index(["retail_feature", "mobility_feature"])
    assert t.loc[("poi_per_km2", "taxi_total"), "consistent"]
    assert not t.loc[("diversity", "bike_total"), "same_sign"] and not t.loc[("diversity", "bike_total"), "consistent"]
    assert t.loc[("share_fashion", "taxi_rush_share"), "same_sign"] and not t.loc[("share_fashion", "taxi_rush_share"), "consistent"]
    assert ("share_services", "bike_total") not in t.index                 # all-NaN pair is dropped
    first = mm.correlation_consistency(c).iloc[0]
    assert first["consistent"] and first["retail_feature"] == "poi_per_km2"   # consistent pairs sorted first


def test_single_month_is_never_called_consistent(tables):
    c, _ = mm.stack(tables, "retail_mobility_correlations_{ym}.csv", MONTHS[:1])
    assert not mm.correlation_consistency(c)["consistent"].any()


def test_weather_effect_and_sensitivity(tables):
    e, _ = mm.stack(tables, "weather_effect_{ym}.csv", MONTHS)
    t = mm.weather_effect_table(e).set_index(["flag", "metric"])
    assert t.loc[("is_wet", "bike_starts_hubs"), "mean_change_pct"] == pytest.approx(-31.0)
    s = mm.sensitivity_consistency(e).set_index("flag")
    assert s.loc["is_wet", "same_every_month"] and s.loc["is_wet", "more_sensitive"] == "bike_starts_hubs"
    assert not s.loc["is_cold", "same_every_month"] and s.loc["is_cold", "more_sensitive"] == "varies"


def test_render_report(tables):
    stats, _ = mm.stack(tables, "hub_rhythm_stats_{ym}.csv", MONTHS)
    corr, _ = mm.stack(tables, "retail_mobility_correlations_{ym}.csv", MONTHS)
    eff, _ = mm.stack(tables, "weather_effect_{ym}.csv", MONTHS)
    md = mm.render_report(MONTHS, mm.monthly_overview(tables, MONTHS), mm.label_stability(stats),
                          mm.rank_stability(stats), mm.correlation_consistency(corr),
                          mm.weather_effect_table(eff), mm.sensitivity_consistency(eff))
    assert md.startswith("# Day 11: Multi-Month Comparison (2024-01 to 2024-03)")
    assert "of 18 hub-metric combinations" in md and "Hub H03" in md
    assert "changed sign" in md and "diversity vs bike_total" in md
    assert "**bike_starts_hubs** drops more in every month" in md and "it varies" in md
    one = mm.render_report(MONTHS[:1], mm.monthly_overview(tables, MONTHS[:1]), pd.DataFrame(), pd.DataFrame(),
                           pd.DataFrame(), pd.DataFrame(), pd.DataFrame())
    assert "Only one month available" in one


def test_empty_correlations_do_not_crash():
    assert mm.correlation_consistency(pd.DataFrame()).empty
