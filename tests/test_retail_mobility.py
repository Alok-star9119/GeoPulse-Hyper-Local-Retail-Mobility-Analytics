import numpy as np
import pandas as pd
import pytest

from geopulse import retail_mobility as rm


@pytest.fixture
def osm():
    """Ten hubs with hand-made category counts (NOT real OSM data)."""
    rows = []
    for i in range(10):
        rows.append({"hub_id": f"H{i+1:02d}", "hub_name": f"Hub {i+1}", "hub_type": "mixed", "radius_m": 500,
                     "poi_total": 0, "poi_per_km2": 0.0, "named_share": 0.9,
                     "food_beverage": 10 * (i + 1), "fashion": 5 * (i + 1) if i % 2 == 0 else 0,
                     "services": 3})
    df = pd.DataFrame(rows)
    df["poi_total"] = df[["food_beverage", "fashion", "services"]].sum(axis=1)
    df["poi_per_km2"] = (df["poi_total"] / 0.785).round(1)
    return df


@pytest.fixture
def stats(osm):
    """Day 9-style stats: taxi total rises with POI density; bike has no data for two hubs."""
    rows = []
    for i, r in enumerate(osm.itertuples()):
        rows.append({"metric": "taxi_pickups", "hub_id": r.hub_id, "total": int(r.poi_total * 100 + i),
                     "rush_share": 0.2 + 0.01 * i, "midday_share": 0.2, "evening_share": 0.15,
                     "weekend_ratio": 1.0, "rhythm": "all-day mixed"})
        has = i >= 2
        rows.append({"metric": "bike_starts", "hub_id": r.hub_id, "total": int(r.poi_total * 10) if has else 0,
                     "rush_share": 0.3 if has else np.nan, "midday_share": 0.2 if has else np.nan,
                     "evening_share": 0.1 if has else np.nan, "weekend_ratio": 0.8 if has else np.nan,
                     "rhythm": "commuter" if has else "no data"})
    return pd.DataFrame(rows)


def test_diversity_extremes():
    assert rm.diversity(pd.Series([5, 5, 5, 5])) == pytest.approx(1.0)
    assert rm.diversity(pd.Series([20, 0, 0, 0])) == 0.0
    assert np.isnan(rm.diversity(pd.Series([0, 0, 0])))
    assert 0 < rm.diversity(pd.Series([10, 5, 1])) < 1


def test_retail_features(osm):
    f = rm.retail_features(osm).set_index("hub_id")
    assert rm.category_columns(osm) == ["food_beverage", "fashion", "services"]
    assert f.loc["H02", "share_fashion"] == 0.0                      # odd-index hubs have no fashion
    assert f.loc["H01", "share_food_beverage"] == pytest.approx(10 / 18, abs=0.001)
    assert f.loc["H10", "dominant_category"] == "food_beverage"
    assert (f[[c for c in f.columns if c.startswith("share_")]].sum(axis=1).round(2) == 1.0).all()


def test_empty_hub_features():
    osm = pd.DataFrame({"hub_id": ["H1"], "hub_name": ["x"], "hub_type": ["y"], "radius_m": [500],
                        "poi_total": [0], "poi_per_km2": [0.0], "named_share": [0.0], "fashion": [0], "services": [0]})
    f = rm.retail_features(osm).iloc[0]
    assert pd.isna(f["diversity"]) and f["dominant_category"] is None and np.isnan(f["dominant_share"])


def test_feature_table_and_per_poi_rule(osm, stats):
    f = rm.hub_feature_table(osm, stats).set_index("hub_id")
    assert {"taxi_total", "bike_total", "taxi_rhythm", "bike_rhythm"} <= set(f.columns)
    assert f.loc["H10", "taxi_per_100_poi"] == pytest.approx((f.loc["H10", "taxi_total"] / f.loc["H10", "poi_total"]) * 100, abs=0.1)
    assert np.isnan(f.loc["H01", "bike_per_100_poi"]) and np.isnan(f.loc["H02", "bike_per_100_poi"])   # no bike data != 0 per POI
    assert not np.isnan(f.loc["H05", "bike_per_100_poi"])


def test_spearman_perfect_and_inverse():
    x = list(range(10))
    rho, n, p = rm.spearman(x, [v ** 2 for v in x])
    assert rho == pytest.approx(1.0) and n == 10 and p < 0.01
    rho2, _, _ = rm.spearman(x, [-v for v in x])
    assert rho2 == pytest.approx(-1.0)


def test_spearman_matches_scipy_with_ties():
    scipy_stats = pytest.importorskip("scipy.stats")
    x = [1, 2, 2, 4, 5, 6, 7, 7, 9, 10]
    y = [2, 1, 4, 3, 6, 5, 9, 8, 7, 10]
    rho, n, _ = rm.spearman(x, y)
    assert rho == pytest.approx(scipy_stats.spearmanr(x, y)[0], abs=1e-9)


def test_spearman_guards():
    assert np.isnan(rm.spearman([1, 2, 3], [1, 2, 3])[0])                    # fewer than MIN_N hubs
    assert np.isnan(rm.spearman([1] * 8, list(range(8)))[0])                 # constant column
    rho, n, _ = rm.spearman([1, 2, 3, 4, 5, 6, np.nan], [2, 1, 4, 3, 6, 5, 9])
    assert n == 6                                                             # NaN rows dropped
    a = rm.spearman(range(10), [3, 1, 4, 1, 5, 9, 2, 6, 5, 3])
    assert a == rm.spearman(range(10), [3, 1, 4, 1, 5, 9, 2, 6, 5, 3])      # deterministic (fixed seed)


def test_random_data_is_not_significant():
    rng = np.random.default_rng(1)
    ps = [rm.spearman(rng.random(10), rng.random(10))[2] for _ in range(20)]
    assert sum(p < 0.05 for p in ps) <= 4                                    # roughly 5% expected


def test_correlation_table_finds_planted_relationship(osm, stats):
    f = rm.hub_feature_table(osm, stats)
    x, y = rm.default_columns(f)
    assert "poi_per_km2" in x and "taxi_total" in y and "bike_weekend_ratio" in y
    c = rm.correlation_table(f, x, y)
    top = c.iloc[0]
    assert abs(top["rho"]) >= 0.95 and top["strength"] == "strong"
    row = c[(c.retail_feature == "poi_per_km2") & (c.mobility_feature == "taxi_total")].iloc[0]
    assert row["rho"] == pytest.approx(1.0, abs=0.01) and row["n_hubs"] == 10
    bike = c[(c.retail_feature == "poi_per_km2") & (c.mobility_feature == "bike_total")].iloc[0]
    assert bike["n_hubs"] == 8                                                # two hubs without bike data excluded
    assert list(c["rho"].abs().dropna()) == sorted(c["rho"].abs().dropna(), reverse=True)


def test_rhythm_group_summary(osm, stats):
    f = rm.hub_feature_table(osm, stats)
    g = rm.rhythm_group_summary(f, "bike_rhythm").set_index("bike_rhythm")
    assert g.loc["no data", "n_hubs"] == 2 and g.loc["commuter", "n_hubs"] == 8
    assert rm.rhythm_group_summary(f, "missing_col").empty


def test_render_report(osm, stats):
    f = rm.hub_feature_table(osm, stats)
    x, y = rm.default_columns(f)
    md = rm.render_report(f, rm.correlation_table(f, x, y), "2024-01")
    assert md.startswith("# Day 10: Retail Mix vs Mobility (2024-01)")
    assert "Taxi trips per 100 POIs" in md and "Strongest rank correlations" in md and "by pure chance" in md
