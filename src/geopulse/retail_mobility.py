"""Day 10: relate the retail mix around each hub (OpenStreetMap, Day 4) to how people move there
(taxi and bike rhythm from Days 8-9).

With only ten hubs, everything here is EXPLORATORY: correlations are rank-based, reported with the
number of hubs used and a permutation p-value, and many pairs are tested, so a few "significant"
results are expected by chance. Use them to generate questions, not to prove causes.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

NON_CATEGORY_COLS = {"hub_id", "hub_name", "hub_type", "radius_m", "poi_total", "poi_per_km2", "named_share"}
PREFIX = {"taxi_pickups": "taxi", "bike_starts": "bike"}
MOBILITY_COLS = ["total", "rush_share", "midday_share", "evening_share", "weekend_ratio"]
MIN_N = 5                      # fewest hubs needed to report a correlation
N_PERM = 5000


# ---------- retail features ----------
def category_columns(osm: pd.DataFrame) -> list[str]:
    return [c for c in osm.columns if c not in NON_CATEGORY_COLS and pd.api.types.is_numeric_dtype(osm[c])]


def diversity(counts: pd.Series) -> float:
    """Normalised Shannon entropy of category counts: 0 = one category only, 1 = perfectly even."""
    c = counts[counts > 0].astype(float)
    if len(c) <= 1 or len(counts) <= 1:
        return 0.0 if c.sum() > 0 else np.nan
    p = c / c.sum()
    return float(-(p * np.log(p)).sum() / np.log(len(counts)))


def retail_features(osm: pd.DataFrame) -> pd.DataFrame:
    """Category shares, diversity and dominant category per hub (input: osm_hub_summary)."""
    cats = category_columns(osm)
    out = osm[["hub_id", "hub_name", "hub_type", "poi_total", "poi_per_km2"]].copy()
    total = osm[cats].sum(axis=1).replace(0, np.nan)
    for c in cats:
        out[f"share_{c}"] = (osm[c] / total).round(3)
    out["diversity"] = osm[cats].apply(diversity, axis=1).round(3)
    has = osm[cats].sum(axis=1) > 0
    out["dominant_category"] = np.where(has, osm[cats].idxmax(axis=1), None)
    out["dominant_share"] = np.where(has, (osm[cats].max(axis=1) / total).round(3), np.nan)
    return out


# ---------- mobility features ----------
def mobility_wide(stats: pd.DataFrame) -> pd.DataFrame:
    """One row per hub with taxi_* and bike_* columns (input: hub_rhythm_stats from Day 9)."""
    wide = pd.DataFrame({"hub_id": stats["hub_id"].unique()})
    for metric, pre in PREFIX.items():
        s = stats[stats["metric"] == metric]
        if s.empty:
            continue
        cols = [c for c in MOBILITY_COLS + ["rhythm"] if c in s.columns]
        part = s[["hub_id"] + cols].rename(columns={c: f"{pre}_{c}" for c in cols})
        if f"{pre}_total" in part.columns:                      # total 0 = no data (no station / zone), not "no demand"
            part[f"{pre}_total"] = part[f"{pre}_total"].where(part[f"{pre}_total"] > 0)
        wide = wide.merge(part, on="hub_id", how="left")
    return wide


def hub_feature_table(osm: pd.DataFrame, stats: pd.DataFrame) -> pd.DataFrame:
    """Retail and mobility features side by side, plus trips per 100 POIs.

    Trips per 100 POIs is NaN when a hub has no trips (no data), because zero then usually means
    'no station / no zone assigned' rather than 'nobody travels here'.
    """
    f = retail_features(osm).merge(mobility_wide(stats), on="hub_id", how="left")
    for pre in ("taxi", "bike"):
        if f"{pre}_total" in f.columns:
            ok = (f["poi_total"] > 0) & (f[f"{pre}_total"] > 0)
            f[f"{pre}_per_100_poi"] = np.where(ok, (f[f"{pre}_total"] / f["poi_total"] * 100).round(1), np.nan)
    return f


# ---------- statistics ----------
def spearman(x, y, n_perm: int = N_PERM, seed: int = 0) -> tuple[float, int, float]:
    """Spearman rank correlation with a permutation p-value (two-sided). Returns (rho, n, p)."""
    d = pd.DataFrame({"x": pd.to_numeric(pd.Series(list(x)), errors="coerce"),
                      "y": pd.to_numeric(pd.Series(list(y)), errors="coerce")}).dropna()
    n = len(d)
    if n < MIN_N:
        return np.nan, n, np.nan
    rx, ry = d["x"].rank().to_numpy(), d["y"].rank().to_numpy()
    rxc, ryc = rx - rx.mean(), ry - ry.mean()
    denom = np.sqrt((rxc ** 2).sum() * (ryc ** 2).sum())
    if denom == 0:
        return np.nan, n, np.nan
    rho = float(rxc @ ryc / denom)
    rng = np.random.default_rng(seed)
    perm_idx = rng.random((n_perm, n)).argsort(axis=1)
    perm_rho = (ryc[perm_idx] @ rxc) / denom
    p = (np.sum(np.abs(perm_rho) >= abs(rho) - 1e-12) + 1) / (n_perm + 1)
    return rho, n, float(p)


def strength(rho: float) -> str:
    if pd.isna(rho):
        return "n/a"
    a = abs(rho)
    return "strong" if a >= 0.6 else "moderate" if a >= 0.3 else "weak"


def correlation_table(features: pd.DataFrame, x_cols: list[str], y_cols: list[str]) -> pd.DataFrame:
    """Spearman correlation of every retail column with every mobility column."""
    rows = []
    for x in x_cols:
        for y in y_cols:
            rho, n, p = spearman(features[x], features[y])
            rows.append({"retail_feature": x, "mobility_feature": y, "n_hubs": n,
                         "rho": round(rho, 2) if not pd.isna(rho) else np.nan,
                         "p_value": round(p, 3) if not pd.isna(p) else np.nan,
                         "strength": strength(rho),
                         "direction": "n/a" if pd.isna(rho) else ("positive" if rho > 0 else "negative")})
    out = pd.DataFrame(rows)
    return out.reindex(out["rho"].abs().sort_values(ascending=False, na_position="last").index).reset_index(drop=True)


def default_columns(features: pd.DataFrame) -> tuple[list[str], list[str]]:
    x = [c for c in ["poi_per_km2", "diversity"] if c in features.columns]
    x += [c for c in features.columns if c.startswith("share_")]
    y = [f"{pre}_{m}" for pre in ("taxi", "bike") for m in MOBILITY_COLS if f"{pre}_{m}" in features.columns]
    return x, y


def rhythm_group_summary(features: pd.DataFrame, rhythm_col: str) -> pd.DataFrame:
    """Average retail profile of hubs that share a rhythm label (small groups: read with care)."""
    if rhythm_col not in features.columns:
        return pd.DataFrame()
    cols = [c for c in ["poi_per_km2", "diversity"] + [c for c in features.columns if c.startswith("share_")]
            if c in features.columns]
    g = features.groupby(rhythm_col)
    out = g[cols].mean().round(3)
    out.insert(0, "n_hubs", g.size())
    return out.reset_index()


# ---------- report ----------
def render_report(features: pd.DataFrame, corr: pd.DataFrame, ym: str) -> str:
    L = [f"# Day 10: Retail Mix vs Mobility ({ym})", "",
         "Generated by `scripts/retail_vs_mobility.py`. **Exploratory:** about ten hubs, one month, many pairs tested.", "",
         "## Retail profile of each hub", "",
         "| Hub | Type | POIs | POIs/km2 | Dominant category | Dominant share | Diversity (0-1) |", "|---|---|---|---|---|---|---|"]
    for r in features.sort_values("poi_total", ascending=False).itertuples():
        dom = "-" if pd.isna(r.dominant_category) or r.dominant_category is None else r.dominant_category
        ds = "-" if pd.isna(r.dominant_share) else f"{r.dominant_share:.0%}"
        dv = "-" if pd.isna(r.diversity) else f"{r.diversity:.2f}"
        L.append(f"| {r.hub_name} | {r.hub_type} | {int(r.poi_total)} | {r.poi_per_km2} | {dom} | {ds} | {dv} |")
    for pre in ("taxi", "bike"):
        col = f"{pre}_per_100_poi"
        if col in features.columns and features[col].notna().any():
            f = features.dropna(subset=[col]).sort_values(col, ascending=False)
            L += ["", f"## {pre.title()} trips per 100 POIs (mobility relative to retail supply)", "",
                  "| Hub | Trips per 100 POIs | POIs | Trips |", "|---|---|---|---|"]
            for r in f.itertuples():
                L.append(f"| {r.hub_name} | {getattr(r, col)} | {int(r.poi_total)} | {int(getattr(r, f'{pre}_total')):,} |")
    L += ["", "## Strongest rank correlations", "",
          "Spearman rho (-1 to 1) with permutation p-value. `n_hubs` is how many hubs had data for both columns.", "",
          "| Retail feature | Mobility feature | n hubs | rho | p | Strength |", "|---|---|---|---|---|---|"]
    for r in corr.dropna(subset=["rho"]).head(10).itertuples():
        L.append(f"| {r.retail_feature} | {r.mobility_feature} | {r.n_hubs} | {r.rho} | {r.p_value} | {r.strength} {r.direction} |")
    n_tests = int(corr["rho"].notna().sum())
    L += ["", "## How to read this",
          f"- {n_tests} correlations were computed. At p < 0.05 about {n_tests * 0.05:.0f} would appear by pure chance, so treat single hits with suspicion and look for consistent patterns across taxi and bike.",
          "- Trips per 100 POIs is a rough index. A high value may mean a hub attracts many trips for its size (a gap in retail supply?) or simply that OpenStreetMap under-counts shops there. Check both before concluding.",
          "- Correlation does not show cause: dense retail may attract trips, or busy places may attract retail.",
          "- Hubs with no trips (no bike stations, no zone) are left out of the affected columns, not counted as zero.", ""]
    return "\n".join(L)
