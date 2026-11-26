"""Day 17: two small experiments that test assumptions made earlier in the project.

Experiment A - do the rule-based rhythm labels (Day 9) match what the data itself groups together?
    k-means on each hub's normalised weekday + weekend hourly profile, compared with the labels by
    adjusted Rand index (ARI: 1 = identical grouping, about 0 = no better than chance).
Experiment B - does rain matter more at some times of day, and does modelling that improve forecasts?
    Rain effect per daypart (Day 6 method) and a forecast ablation with a rain x daypart interaction (Day 13).
Everything is numpy/pandas only. With about ten hubs the results are suggestive, not conclusive.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from geopulse import forecast as fc
from geopulse.panel import weather_effect

DAYPARTS = {"night (00-05)": range(0, 6), "morning (06-09)": range(6, 10), "midday (10-15)": range(10, 16),
            "evening (16-19)": range(16, 20), "late (20-23)": range(20, 24)}


# ---------- clustering helpers ----------
def kmeans(X: np.ndarray, k: int, n_init: int = 10, seed: int = 0, iters: int = 100) -> tuple[np.ndarray, float]:
    """Plain k-means with k-means++ starts; returns (labels, inertia) of the best of n_init runs."""
    rng = np.random.default_rng(seed)
    best = (None, np.inf)
    for _ in range(n_init):
        centers = [X[rng.integers(len(X))]]
        for _ in range(k - 1):
            d2 = np.min([((X - c) ** 2).sum(axis=1) for c in centers], axis=0)
            p = d2 / d2.sum() if d2.sum() > 0 else None
            centers.append(X[rng.choice(len(X), p=p)])
        C = np.array(centers)
        for _ in range(iters):
            lab = ((X[:, None, :] - C[None]) ** 2).sum(axis=2).argmin(axis=1)
            newC = np.array([X[lab == j].mean(axis=0) if (lab == j).any() else X[rng.integers(len(X))] for j in range(k)])
            if np.allclose(newC, C):
                break
            C = newC
        inertia = float(((X - C[lab]) ** 2).sum())
        if inertia < best[1]:
            best = (lab, inertia)
    return best


def silhouette(X: np.ndarray, lab: np.ndarray) -> float:
    """Mean silhouette (-1 to 1; higher = clearer clusters). Singleton clusters score 0."""
    D = np.sqrt(((X[:, None, :] - X[None]) ** 2).sum(axis=2))
    s = []
    for i in range(len(X)):
        same = (lab == lab[i]) & (np.arange(len(X)) != i)
        if not same.any():
            s.append(0.0)
            continue
        a = D[i, same].mean()
        b = min(D[i, lab == j].mean() for j in set(lab) if j != lab[i])
        s.append((b - a) / max(a, b) if max(a, b) > 0 else 0.0)
    return float(np.mean(s))


def adjusted_rand(a, b) -> float:
    """Adjusted Rand index between two groupings of the same items."""
    a, b = pd.factorize(pd.Series(list(a)))[0], pd.factorize(pd.Series(list(b)))[0]
    n = len(a)
    if n < 2:
        return float("nan")
    ct = pd.crosstab(a, b).to_numpy()
    c2 = lambda x: x * (x - 1) / 2
    sum_ij, sum_a, sum_b = c2(ct).sum(), c2(ct.sum(axis=1)).sum(), c2(ct.sum(axis=0)).sum()
    expected = sum_a * sum_b / c2(n)
    max_idx = (sum_a + sum_b) / 2
    return 1.0 if max_idx == expected else float((sum_ij - expected) / (max_idx - expected))


# ---------- Experiment A ----------
def hub_profile_matrix(rhythm: pd.DataFrame, metric: str) -> pd.DataFrame:
    """Hub x 48 matrix: share of daily volume per hour, weekday then weekend. Hubs with no data are dropped."""
    r = rhythm[rhythm["metric"] == metric]
    m = r.pivot_table(index="hub_name", columns=["day_type", "hour"], values="share", aggfunc="mean")
    return m.dropna(how="any").loc[lambda d: d.sum(axis=1) > 0]


def cluster_hubs(rhythm: pd.DataFrame, stats: pd.DataFrame, metric: str, ks=(2, 3, 4), seed: int = 0) -> tuple[pd.DataFrame, dict]:
    """Cluster hubs by profile shape; pick k by silhouette; compare with the rule-based labels."""
    M = hub_profile_matrix(rhythm, metric)
    if len(M) < 4:
        return pd.DataFrame(), {"metric": metric, "status": f"only {len(M)} hubs with data; need at least 4"}
    X = M.to_numpy()
    scores = {}
    for k in ks:
        if k < len(M):
            lab, _ = kmeans(X, k, seed=seed)
            scores[k] = (silhouette(X, lab), lab)
    k = max(scores, key=lambda j: scores[j][0])
    sil, lab = scores[k]
    out = pd.DataFrame({"metric": metric, "hub_name": M.index, "cluster": lab})
    wk_peak = M["weekday"].idxmax(axis=1)
    out["weekday_peak_hour"] = out["hub_name"].map(wk_peak)
    rule = stats[stats["metric"] == metric].groupby("hub_name")["rhythm"].agg(lambda s: s.mode().iloc[0])
    out["rule_label"] = out["hub_name"].map(rule)
    seeds = [adjusted_rand(lab, kmeans(X, k, seed=s)[0]) for s in range(1, 6)]
    summary = {"metric": metric, "status": "ok", "n_hubs": len(M), "k": k, "silhouette": round(sil, 2),
               "ari_vs_rule_labels": round(adjusted_rand(out["cluster"], out["rule_label"]), 2),
               "ari_seed_stability": round(float(np.nanmean(seeds)), 2),
               "silhouette_by_k": "; ".join(f"k={j}: {v[0]:.2f}" for j, v in scores.items())}
    return out, summary


# ---------- Experiment B ----------
def rain_by_daypart(panel: pd.DataFrame, metrics: list[str], flag: str = "is_wet") -> pd.DataFrame:
    rows = []
    for name, hours in DAYPARTS.items():
        sub = panel[panel["hour"].isin(list(hours))]
        if not sub[flag].any():
            continue
        e = weather_effect(sub, metrics, flag)
        e.insert(0, "daypart", name)
        rows.append(e)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=["daypart", "flag", "metric", "change_pct"])


def _daypart_design(df: pd.DataFrame, tm: float) -> np.ndarray:
    """wet x each daypart, snow, temperature: lets the rain effect differ by time of day."""
    wet = df["is_wet"].fillna(False).astype(float).to_numpy()
    snow = df["is_snow"].fillna(False).astype(float).to_numpy()
    temp = df["temp_c"].fillna(tm).to_numpy(dtype=float) - tm
    hr = df["datetime"].dt.hour.to_numpy()
    cols = [wet * np.isin(hr, list(h)) for h in DAYPARTS.values()]
    return np.column_stack(cols + [snow, temp])


def forecast_ablation(df: pd.DataFrame, target: str, test_days: int = 7) -> pd.DataFrame:
    """WAPE with: hour-of-week only, additive weather, and rain x daypart interaction."""
    train, test = fc.split_by_days(df, test_days)
    actual = test[target].to_numpy(dtype=float)
    hm = fc.hour_of_week_mean(train, target)
    rows = [{"model": "hour_of_week", **fc.metrics(actual, hm.reindex(fc.how_key(test)).to_numpy())}]
    for name, design in (("additive_weather", None), ("rain_by_daypart", _daypart_design)):
        lv, coef, tm = fc.fit_weather_model(train, target, design=design)
        rows.append({"model": name, **fc.metrics(actual, fc.predict_weather(test, lv, coef, tm, design))})
    out = pd.DataFrame(rows)
    out.insert(0, "target", target)
    return out


def render_report(ym: str, summaries: list[dict], clusters: pd.DataFrame, rain: pd.DataFrame, ablation: pd.DataFrame) -> str:
    L = [f"# Day 17: Experiments ({ym})", "", "Two experiments that test earlier assumptions. Suggestive only: about ten hubs, one month.", "",
         "## A. Do data-driven clusters match the rhythm labels?", ""]
    ok = [s for s in summaries if s.get("status") == "ok"]
    for s in summaries:
        if s.get("status") != "ok":
            L.append(f"- {s['metric']}: not run ({s['status']}).")
    if ok:
        L += ["| Metric | Hubs | Best k | Silhouette | ARI vs rule labels | ARI across seeds |", "|---|---|---|---|---|---|"]
        L += [f"| {s['metric']} | {s['n_hubs']} | {s['k']} | {s['silhouette']} | {s['ari_vs_rule_labels']} | {s['ari_seed_stability']} |" for s in ok]
        L += ["", "ARI near 1 means the data groups hubs the same way the rules do; near 0 means the rule labels add little over chance.",
              "Silhouette above about 0.5 suggests clear clusters; below 0.25 suggests the hubs form a continuum.", ""]
    if len(clusters):
        L += ["| Metric | Hub | Cluster | Weekday peak hour | Rule label |", "|---|---|---|---|---|"]
        L += [f"| {r.metric} | {r.hub_name} | {r.cluster} | {r.weekday_peak_hour}:00 | {r.rule_label} |" for r in clusters.sort_values(["metric", "cluster"]).itertuples()]
    L += ["", "## B. Does rain matter more at some times of day?", ""]
    if len(rain):
        L += ["| Daypart | Metric | Change in wet hours |", "|---|---|---|"]
        L += [f"| {r.daypart} | {r.metric} | {'n/a' if pd.isna(r.change_pct) else f'{r.change_pct:+.1f}%'} |" for r in rain.itertuples()]
    else:
        L.append("No wet hours in the data.")
    if len(ablation):
        L += ["", "Forecast ablation (WAPE %, last 7 days, lower is better):", "", "| Target | Model | WAPE % | MAE |", "|---|---|---|---|"]
        L += [f"| {r.target} | {r.model} | {r.wape_pct} | {r.mae} |" for r in ablation.itertuples()]
        L += ["", "If `rain_by_daypart` is not clearly below `additive_weather`, the extra complexity is not justified by this data."]
    L += ["", "## Caveats", "- k-means on ten points is sensitive to the start; the across-seed ARI shows how much.",
          "- Few wet hours per daypart make single-daypart effects noisy.", "- Experiments, not findings: confirm on more months before using them in the report.", ""]
    return "\n".join(L)
