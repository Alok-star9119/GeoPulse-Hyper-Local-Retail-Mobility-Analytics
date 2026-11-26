"""Day 13: simple hourly demand forecasts, to see how predictable the patterns are.

Three baselines, all numpy-only and easy to explain:
  1. seasonal naive:   the value one week earlier (same weekday and hour)
  2. hour-of-week mean: average of the training weeks for that weekday and hour
  3. hour-of-week + weather: hour-of-week levels fitted together with a linear effect of rain, snow and temperature
Evaluation is time-ordered: the last N days of the month are the test set, never shuffled.
These are baselines, not production forecasts; a month has only 3-4 weeks of history.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

WEEK = 168
WEATHER_COLS = ["is_wet", "is_snow", "temp_c"]


def split_by_days(df: pd.DataFrame, test_days: int = 7) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Train = everything before the last `test_days` calendar days; test = those days."""
    df = df.sort_values("datetime").reset_index(drop=True)
    cut = df["datetime"].dt.normalize().max() - pd.Timedelta(days=test_days - 1)
    train, test = df[df["datetime"] < cut], df[df["datetime"] >= cut]
    if len(train) < 2 * WEEK:
        raise ValueError(f"Need at least 14 training days, got {len(train) / 24:.1f}")
    return train, test


def how_key(df: pd.DataFrame) -> pd.Series:
    return df["datetime"].dt.dayofweek * 24 + df["datetime"].dt.hour


def hour_of_week_mean(train: pd.DataFrame, target: str) -> pd.Series:
    """Mean per (weekday, hour) over the training weeks; indexed by 0..167."""
    m = train.groupby(how_key(train))[target].mean()
    return m.reindex(range(WEEK)).fillna(train[target].mean())


def seasonal_naive(full: pd.DataFrame, test: pd.DataFrame, target: str) -> np.ndarray:
    """Value 168 hours earlier, looked up in the full series (earlier than the test hour, so no leak)."""
    s = full.set_index("datetime")[target]
    return s.reindex(test["datetime"] - pd.Timedelta(hours=WEEK)).to_numpy(dtype=float)


def _design(df: pd.DataFrame, temp_mean: float) -> np.ndarray:
    """Columns: wet, snow, temperature minus training mean (no intercept; the hour-of-week level carries it)."""
    wet = df["is_wet"].fillna(False).astype(float).to_numpy()
    snow = df["is_snow"].fillna(False).astype(float).to_numpy()
    temp = df["temp_c"].fillna(temp_mean).to_numpy(dtype=float) - temp_mean
    return np.column_stack([wet, snow, temp])


def fit_weather_model(train: pd.DataFrame, target: str, iterations: int = 20, design=None) -> tuple[pd.Series, np.ndarray, float]:
    """Fit hour-of-week levels and weather coefficients together (backfitting).

    A plain hour-of-week mean already contains the rain that fell in those hours, so regressing its
    residual on rain would understate the rain effect. Alternating the two fits removes that bias.
    Returns (hour-of-week levels, coefficients [wet, snow, temp per C], mean training temperature).
    """
    design = design or _design                                # a different design matrix lets experiments add interactions
    y = train[target].to_numpy(dtype=float)
    tm = float(train["temp_c"].mean()) if train["temp_c"].notna().any() else 0.0
    X = design(train, tm)
    live = np.abs(X).sum(axis=0) > 0                          # a flag that never occurs cannot be estimated
    key = how_key(train).to_numpy()
    coef = np.zeros(X.shape[1])
    for _ in range(iterations):
        lvl = pd.Series(y - X @ coef).groupby(key).mean().reindex(range(WEEK))
        lvl = lvl.fillna(float(np.nanmean(y - X @ coef)))
        resid = y - lvl.to_numpy()[key]
        if live.any():
            coef[live] = np.linalg.lstsq(X[:, live], resid, rcond=None)[0]
    return lvl, coef, tm


def predict_weather(test: pd.DataFrame, levels: pd.Series, coef: np.ndarray, tm: float, design=None) -> np.ndarray:
    base = levels.reindex(how_key(test)).to_numpy()
    return np.clip(base + (design or _design)(test, tm) @ coef, 0, None)


def metrics(actual, pred) -> dict:
    a, p = np.asarray(actual, float), np.asarray(pred, float)
    ok = ~np.isnan(a) & ~np.isnan(p)
    a, p = a[ok], p[ok]
    if len(a) == 0:
        return {"n": 0, "mae": np.nan, "wape_pct": np.nan, "bias_pct": np.nan}
    err = p - a
    tot = a.sum()
    return {"n": int(len(a)), "mae": round(float(np.abs(err).mean()), 2),
            "wape_pct": round(float(100 * np.abs(err).sum() / tot), 1) if tot > 0 else np.nan,
            "bias_pct": round(float(100 * err.sum() / tot), 1) if tot > 0 else np.nan}


def evaluate(df: pd.DataFrame, target: str, test_days: int = 7) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (metrics per model, test-period predictions). WAPE = total absolute error / total actual."""
    train, test = split_by_days(df, test_days)
    hm = hour_of_week_mean(train, target)
    levels, coef, tm = fit_weather_model(train, target)
    preds = pd.DataFrame({"datetime": test["datetime"].to_numpy(), "actual": test[target].to_numpy(dtype=float),
                          "seasonal_naive": seasonal_naive(df, test, target),
                          "hour_of_week": hm.reindex(how_key(test)).to_numpy(),
                          "hour_of_week_weather": predict_weather(test, levels, coef, tm)})
    rows = [{"model": m, **metrics(preds["actual"], preds[m])} for m in ("seasonal_naive", "hour_of_week", "hour_of_week_weather")]
    out = pd.DataFrame(rows)
    out.insert(0, "target", target)
    out["train_days"] = round(len(train) / 24, 1)
    out["test_days"] = test_days
    out["wet_effect"] = round(float(coef[0]), 2)
    out["snow_effect"] = round(float(coef[1]), 2)
    out["temp_effect_per_c"] = round(float(coef[2]), 2)
    return out, preds


def hub_evaluation(hub_panel: pd.DataFrame, target: str, test_days: int = 7) -> pd.DataFrame:
    """Hour-of-week and weather model per hub. Hubs with no training volume are reported as no data."""
    rows = []
    for (hid, name), g in hub_panel.groupby(["hub_id", "hub_name"], sort=False):
        if target not in g.columns or g[target].fillna(0).sum() == 0:
            rows.append({"target": target, "hub_id": hid, "hub_name": name, "status": "no data"})
            continue
        res, _ = evaluate(g, target, test_days)
        r = res.set_index("model")
        best_base = min(r.loc["seasonal_naive", "wape_pct"], r.loc["hour_of_week", "wape_pct"])
        rows.append({"target": target, "hub_id": hid, "hub_name": name, "status": "ok",
                     "wape_naive": r.loc["seasonal_naive", "wape_pct"], "wape_how": r.loc["hour_of_week", "wape_pct"],
                     "wape_weather": r.loc["hour_of_week_weather", "wape_pct"],
                     "weather_gain_pts": round(float(r.loc["hour_of_week", "wape_pct"] - r.loc["hour_of_week_weather", "wape_pct"]), 1),
                     "best_baseline_wape": best_base})
    return pd.DataFrame(rows)


def render_report(ym: str, city: pd.DataFrame, hubs: pd.DataFrame) -> str:
    L = [f"# Day 13: Forecast Baselines ({ym})", "",
         "How well can simple models predict hourly demand? The last days of the month are held out (time-ordered split). "
         "WAPE = total absolute error / total actual demand (lower is better); bias > 0 means over-prediction.", "",
         "## City level", "", "| Target | Model | MAE (trips/h) | WAPE % | Bias % |", "|---|---|---|---|---|"]
    L += [f"| {r.target} | {r.model} | {r.mae} | {r.wape_pct} | {r.bias_pct} |" for r in city.itertuples()]
    if len(city):
        c = city.iloc[0]
        L += ["", f"Train {c.train_days} days, test {c.test_days} days. Estimated weather effect, in trips per hour (units of the target):", "", "| Target | Rain (wet hour) | Snow | Per +1 C |", "|---|---|---|---|"]
        L += [f"| {t} | {g.wet_effect.iloc[0]} | {g.snow_effect.iloc[0]} | {g.temp_effect_per_c.iloc[0]} |" for t, g in city.groupby("target", sort=False)]
    ok = hubs[hubs["status"] == "ok"] if len(hubs) else hubs
    if len(ok):
        L += ["", "## Per hub", "", "| Target | Hub | WAPE naive | WAPE hour-of-week | WAPE with weather | Weather gain (pts) |", "|---|---|---|---|---|---|"]
        L += [f"| {r.target} | {r.hub_name} | {r.wape_naive} | {r.wape_how} | {r.wape_weather} | {r.weather_gain_pts} |" for r in ok.itertuples()]
        nd = hubs[hubs["status"] != "ok"]
        if len(nd):
            L += ["", "No data (not forecast): " + ", ".join(sorted(set(f"{r.hub_name} ({r.target})" for r in nd.itertuples()))) + "."]
    L += ["", "## Caveats",
          "- One month gives only 3 training weeks; holidays inside the test week are not predictable by these models.",
          "- Seasonal naive copies last week's value, so it inherits last week's noise; the hour-of-week mean averages several weeks.",
          "- Hub-level hourly counts are small, so WAPE is much higher than at city level.",
          "- Weather effects are linear and descriptive; a gain of a few WAPE points means weather explains little beyond the weekly pattern.", ""]
    return "\n".join(L)
