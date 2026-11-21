"""Day 11: compare results across months to see which findings are stable.

A pattern that appears in one month may be chance, weather or a holiday. This module reads the
per-month tables written by Days 6-10 and asks, for each finding: does it hold in every month?
Everything is descriptive; with 10 hubs and a few months, "stable" means "no evidence against".
"""
from __future__ import annotations

import calendar
import re
from pathlib import Path

import numpy as np
import pandas as pd

from geopulse.retail_mobility import spearman

MIN_ABS_RHO = 0.3          # a relationship must be at least this strong, with the same sign, to count as consistent


# ---------- loading ----------
def discover_months(tables: Path, template: str = "hub_rhythm_stats_{ym}.csv") -> list[str]:
    """Months (YYYY-MM) that have the given per-month table, sorted."""
    pat = re.compile("^" + re.escape(template).replace(re.escape("{ym}"), r"(\d{4}-\d{2})") + "$")
    found = [m.group(1) for f in Path(tables).iterdir() if (m := pat.match(f.name))]
    return sorted(found)


def stack(tables: Path, template: str, months: list[str]) -> tuple[pd.DataFrame, list[str]]:
    """Concatenate per-month CSVs, adding a `month` column. Missing files are skipped and reported."""
    frames, found = [], []
    for ym in months:
        f = Path(tables) / template.format(ym=ym)
        if f.exists():
            frames.append(pd.read_csv(f).assign(month=ym))
            found.append(ym)
    return (pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()), found


# ---------- overview ----------
def overview_from_city(city: pd.DataFrame, ym: str) -> dict:
    """City-level totals and weather for one month, plus per-day averages (months differ in length)."""
    y, m = int(ym[:4]), int(ym[5:7])
    days = calendar.monthrange(y, m)[1]
    return {"month": ym, "days": days,
            "taxi_total": int(city["taxi_pickups"].sum()), "bike_total": int(city["bike_starts_hubs"].sum()),
            "taxi_per_day": round(city["taxi_pickups"].sum() / days), "bike_per_day": round(city["bike_starts_hubs"].sum() / days),
            "temp_mean_c": round(float(city["temp_c"].mean()), 1), "precip_mm": round(float(city["precip_mm"].sum()), 1),
            "wet_hours": int((city["precip_mm"] >= 0.1).sum()), "freezing_hours": int((city["temp_c"] <= 0).sum())}


def monthly_overview(tables: Path, months: list[str]) -> pd.DataFrame:
    rows = []
    for ym in months:
        f = Path(tables) / f"city_hourly_panel_{ym}.csv"
        if f.exists():
            rows.append(overview_from_city(pd.read_csv(f), ym))
    return pd.DataFrame(rows)


# ---------- stability of hub rhythm labels ----------
def label_stability(stats_all: pd.DataFrame) -> pd.DataFrame:
    """For each hub and metric: does the Day 9 rhythm label stay the same in every month?

    Months where the hub has no data are ignored (a coverage gap says nothing about the rhythm).
    """
    s = stats_all[stats_all["rhythm"] != "no data"].sort_values("month")
    rows = []
    for (metric, hid, name), g in s.groupby(["metric", "hub_id", "hub_name"], sort=False):
        labels = list(g["rhythm"])
        rows.append({"metric": metric, "hub_id": hid, "hub_name": name, "n_months": len(g),
                     "stable": g["rhythm"].nunique() == 1,
                     "modal_label": g["rhythm"].mode().iloc[0],
                     "labels_by_month": "; ".join(f"{m}={l}" for m, l in zip(g["month"], labels)),
                     "weekday_peak_hours": "; ".join(f"{m}={int(h)}:00" for m, h in zip(g["month"], g["weekday_peak_hour"]) if pd.notna(h)),
                     "weekend_ratio_min": g["weekend_ratio"].min(), "weekend_ratio_max": g["weekend_ratio"].max()})
    return pd.DataFrame(rows)


# ---------- stability of hub ranking ----------
def rank_stability(stats_all: pd.DataFrame, value: str = "total") -> pd.DataFrame:
    """Do the busiest hubs stay the busiest? Spearman correlation of hub rankings, month by month pair."""
    rows = []
    for metric, g in stats_all.groupby("metric", sort=False):
        piv = g.pivot(index="hub_name", columns="month", values=value).where(lambda d: d > 0)   # 0 = no data
        months = sorted(piv.columns)
        for i, a in enumerate(months):
            for b in months[i + 1:]:
                both = piv[[a, b]].dropna()
                rho, n, _ = spearman(both[a], both[b])
                top = lambda col: set(both[col].nlargest(3).index)
                rows.append({"metric": metric, "month_a": a, "month_b": b, "n_hubs": n,
                             "rho": round(rho, 2) if pd.notna(rho) else np.nan,
                             "top3_overlap": len(top(a) & top(b)) if n >= 3 else np.nan})
    return pd.DataFrame(rows, columns=["metric", "month_a", "month_b", "n_hubs", "rho", "top3_overlap"])


# ---------- consistency of retail-mobility correlations ----------
def correlation_consistency(corr_all: pd.DataFrame, min_abs: float = MIN_ABS_RHO) -> pd.DataFrame:
    """Which Day 10 correlations keep the same sign and a meaningful size in every month?"""
    if corr_all.empty or "rho" not in corr_all.columns:
        return pd.DataFrame()
    rows = []
    for (rf, mf), g in corr_all.dropna(subset=["rho"]).sort_values("month").groupby(["retail_feature", "mobility_feature"]):
        rho = g["rho"]
        same_sign = bool((rho > 0).all() or (rho < 0).all())
        rows.append({"retail_feature": rf, "mobility_feature": mf, "n_months": len(g),
                     "mean_rho": round(float(rho.mean()), 2), "min_rho": float(rho.min()), "max_rho": float(rho.max()),
                     "same_sign": same_sign,
                     "consistent": bool(len(g) >= 2 and same_sign and rho.abs().min() >= min_abs),
                     "rho_by_month": "; ".join(f"{m}={r:.2f}" for m, r in zip(g["month"], rho))})
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values(["consistent", "mean_rho"], key=lambda s: s if s.name == "consistent" else s.abs(),
                           ascending=False).reset_index(drop=True)


# ---------- weather effect across months ----------
def weather_effect_table(eff_all: pd.DataFrame) -> pd.DataFrame:
    """% change in trips in wet / freezing hours, one column per month."""
    t = eff_all.pivot_table(index=["flag", "metric"], columns="month", values="change_pct", aggfunc="first")
    t["mean_change_pct"] = t.mean(axis=1).round(1)
    return t.reset_index()


def sensitivity_consistency(eff_all: pd.DataFrame) -> pd.DataFrame:
    """For each weather flag: which mode drops more, and is that the same in every month?"""
    rows = []
    for flag, g in eff_all.groupby("flag"):
        per_month = {}
        for ym, h in g.groupby("month"):
            h = h.dropna(subset=["change_pct"])
            if len(h) >= 2:
                per_month[ym] = h.loc[h["change_pct"].idxmin(), "metric"]       # most negative = most sensitive
        if per_month:
            vals = set(per_month.values())
            rows.append({"flag": flag, "n_months": len(per_month), "same_every_month": len(vals) == 1,
                         "more_sensitive": next(iter(vals)) if len(vals) == 1 else "varies",
                         "by_month": "; ".join(f"{m}={v}" for m, v in sorted(per_month.items()))})
    return pd.DataFrame(rows, columns=["flag", "n_months", "same_every_month", "more_sensitive", "by_month"])


# ---------- report ----------
def render_report(months: list[str], overview: pd.DataFrame, labels: pd.DataFrame, ranks: pd.DataFrame,
                  corr: pd.DataFrame, weather: pd.DataFrame, sens: pd.DataFrame) -> str:
    L = [f"# Day 11: Multi-Month Comparison ({months[0]} to {months[-1]})", "",
         f"Months compared: {', '.join(months)}. Generated by `scripts/compare_months.py`.",
         "Goal: separate patterns that **repeat in every month** from ones that appeared once. "
         "With ten hubs and a few months this is still exploratory.", ""]
    if len(months) < 2:
        L += ["**Only one month available.** Run `python scripts/run_months.py --months <more months>` first.", ""]
    L += ["## Overview by month", "", "| Month | Days | Taxi/day | Bike/day | Mean temp (C) | Precip (mm) | Wet hours | Freezing hours |",
          "|---|---|---|---|---|---|---|---|"]
    for r in overview.itertuples():
        L.append(f"| {r.month} | {r.days} | {r.taxi_per_day:,} | {r.bike_per_day:,} | {r.temp_mean_c} | {r.precip_mm} | {r.wet_hours} | {r.freezing_hours} |")
    if len(labels):
        n, k = len(labels[labels.n_months >= 2]), int(labels[labels.n_months >= 2]["stable"].sum())
        L += ["", "## Do hub rhythm labels stay the same? (Day 9)", "",
              f"{k} of {n} hub-metric combinations with data in 2+ months kept the same label in every month.", ""]
        changed = labels[(labels.n_months >= 2) & (~labels.stable)]
        if len(changed):
            L += ["| Metric | Hub | Labels by month |", "|---|---|---|"]
            L += [f"| {r.metric} | {r.hub_name} | {r.labels_by_month} |" for r in changed.itertuples()]
        else:
            L.append("No label changed.")
    if len(ranks):
        L += ["", "## Do the busiest hubs stay the busiest? (rank correlation of monthly totals)", "",
              "| Metric | Months | Hubs | rho | Same hubs in top 3 |", "|---|---|---|---|---|"]
        L += [f"| {r.metric} | {r.month_a} vs {r.month_b} | {r.n_hubs} | {r.rho} | {r.top3_overlap}/3 |" for r in ranks.itertuples()]
    if len(corr):
        multi = corr[corr.n_months >= 2]
        good = multi[multi.consistent]
        L += ["", "## Which retail-mobility correlations repeat? (Day 10)", "",
              f"{len(good)} of {len(multi)} correlations seen in 2+ months kept the same sign with |rho| >= {MIN_ABS_RHO} every month.", ""]
        if len(good):
            L += ["| Retail feature | Mobility feature | Months | Mean rho | rho by month |", "|---|---|---|---|---|"]
            L += [f"| {r.retail_feature} | {r.mobility_feature} | {r.n_months} | {r.mean_rho} | {r.rho_by_month} |" for r in good.head(10).itertuples()]
        flips = multi[~multi.same_sign].head(5)
        if len(flips):
            L += ["", "Examples that **changed sign** between months (treat as noise):", ""]
            L += [f"- {r.retail_feature} vs {r.mobility_feature}: {r.rho_by_month}" for r in flips.itertuples()]
    if len(sens):
        L += ["", "## Is one mode more weather-sensitive every month? (Day 6)", ""]
        for r in sens.itertuples():
            word = f"**{r.more_sensitive}** drops more in every month" if r.same_every_month else f"it varies ({r.by_month})"
            L.append(f"- {r.flag}: {word} ({r.n_months} months).")
    L += ["", "## Caveats",
          "- All months are winter / early spring, so seasonal effects (summer cycling, tourism) are not covered.",
          "- Months with a daylight-saving change (March, November) have 23- or 25-hour days; weather gaps are filled and flagged (`weather_filled`).",
          "- Holidays and events differ by month. Check `daily_extremes` before attributing a change to weather or retail.",
          "- A pattern that repeats in 2-3 months is more credible than one month, but still not proof.", ""]
    return "\n".join(L)
