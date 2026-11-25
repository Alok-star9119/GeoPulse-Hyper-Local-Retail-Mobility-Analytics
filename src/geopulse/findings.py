"""Day 16: draft the project findings from the result tables, with every number traceable.

The text is generated from `reports/tables/`, never typed by hand, so it cannot drift from the data.
It is a DRAFT: the author must read it, check it against the dashboard and add interpretation.
Wording stays descriptive (no causal claims) and says "no data" where a hub has no coverage.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from geopulse import keynumbers as kn
from geopulse import multimonth as mm


def coverage_section(tables: Path, months: list[str]) -> list[str]:
    ov = mm.monthly_overview(tables, months)
    L = ["## 1. Coverage", ""]
    if ov.empty:
        return L + ["No processed months found. Run `python scripts/run_months.py` first.", ""]
    L.append(f"Months analysed: {', '.join(ov['month'])} ({int(ov['days'].sum())} days). "
             f"Taxi pickups in the hubs: {int(ov['taxi_total'].sum()):,}; Citi Bike starts at hub stations: {int(ov['bike_total'].sum()):,}.")
    return L + [""]


def hub_section(stats: pd.DataFrame) -> list[str]:
    L = ["## 2. Hub profiles", ""]
    if stats.empty:
        return L + ["No hub rhythm tables found. Run `python scripts/eda_hub_rhythm.py`.", ""]
    for metric, g in stats.groupby("metric", sort=False):
        t = g.groupby("hub_name", sort=False).agg(total=("total", "sum"), rhythm=("rhythm", lambda s: s.mode().iloc[0]))
        ok = t[t["total"] > 0].sort_values("total", ascending=False)
        nodata = list(t[t["total"] <= 0].index)
        if ok.empty:
            L.append(f"- {metric}: no hub has data.")
            continue
        top, low = ok.iloc[0], ok.iloc[-1]
        L.append(f"- **{metric}**: the busiest hub is {ok.index[0]} ({top.total:,.0f} trips, rhythm: {top.rhythm}); "
                 f"the quietest with data is {ok.index[-1]} ({low.total:,.0f}, {low.rhythm}). "
                 f"Rhythm labels: " + ", ".join(f"{k} {v}" for k, v in ok["rhythm"].value_counts().items()) + ".")
        if nodata:
            L.append(f"  - No data (no station or zone in the catchment, not zero demand): {', '.join(nodata)}.")
    return L + [""]


def correlation_section(corr: pd.DataFrame, n_months: int, top: int = 5) -> list[str]:
    L = ["## 3. Retail mix vs mobility", ""]
    c = mm.correlation_consistency(corr) if len(corr) else pd.DataFrame()
    if c.empty:
        return L + ["No correlation tables found. Run `python scripts/retail_vs_mobility.py`.", ""]
    if n_months >= 2:
        good = c[c["consistent"]]
        L.append(f"{len(good)} of {len(c)} retail-mobility rank correlations kept the same sign with |rho| >= {mm.MIN_ABS_RHO} in every month.")
        for r in good.head(top).itertuples():
            L.append(f"- {r.retail_feature} vs {r.mobility_feature}: rho by month {r.rho_by_month}.")
    else:
        for r in c.reindex(c["mean_rho"].abs().sort_values(ascending=False).index).head(top).itertuples():
            L.append(f"- {r.retail_feature} vs {r.mobility_feature}: rho = {r.mean_rho}.")
    L += ["", "Caution: about ten hubs and many tested pairs, so a few strong correlations are expected by chance. "
          "These are associations, not causes.", ""]
    return L


def weather_section(eff: pd.DataFrame) -> list[str]:
    L = ["## 4. Weather", ""]
    if eff.empty:
        return L + ["No weather-effect tables found.", ""]
    for (flag, metric), g in eff.groupby(["flag", "metric"], sort=False):
        v = g["change_pct"].dropna()
        if v.empty:
            continue
        L.append(f"- {flag}, {metric}: {v.mean():+.1f}% on average versus comparable hours ({len(v)} month(s), range {v.min():+.1f}% to {v.max():+.1f}%).")
    return L + [""]


def forecast_section(fc: pd.DataFrame) -> list[str]:
    L = ["## 5. Forecast baselines", ""]
    if fc.empty:
        return L + ["No forecast tables found. Run `python scripts/forecast_baseline.py`.", ""]
    for t, g in fc.groupby("target", sort=False):
        L.append(f"- {t}: WAPE {g['wape_naive'].mean():.1f}% (seasonal naive), {g['wape_hour_of_week'].mean():.1f}% (hour-of-week), "
                 f"{g['wape_with_weather'].mean():.1f}% (with weather); weather changes WAPE by {g['weather_gain_pts'].mean():+.1f} points on average.")
    return L + [""]


def quality_section(q: pd.DataFrame) -> list[str]:
    L = ["## 6. Data quality", ""]
    if q.empty:
        return L + ["No quality tables found. Run `python scripts/quality_review.py`.", ""]
    L.append(f"Checks run: {int(q['checks'].sum())} across {len(q)} month(s): {int(q['pass'].sum())} pass, {int(q['warn'].sum())} warn, {int(q['fail'].sum())} fail.")
    bad = q[q["fail"] > 0]
    if len(bad):
        L.append("Months with failed checks (read `quality_checks_<month>.csv` before using them): " + ", ".join(bad["month"]) + ".")
    return L + [""]


def build(tables: Path, months: list[str]) -> str:
    stats, _ = mm.stack(tables, "hub_rhythm_stats_{ym}.csv", months)
    corr, _ = mm.stack(tables, "retail_mobility_correlations_{ym}.csv", months)
    eff, _ = mm.stack(tables, "weather_effect_{ym}.csv", months)
    L = ["# Findings Draft (generated)", "",
         "Generated from `reports/tables/` by `scripts/build_findings.py`. **Draft**: read it, check the dashboard, then rewrite "
         "in your own words and add interpretation. Descriptive and exploratory only.", ""]
    L += coverage_section(tables, months) + hub_section(stats) + correlation_section(corr, len(months)) + weather_section(eff)
    L += forecast_section(kn.forecast_summary(tables, months)) + quality_section(kn.quality_summary(tables, months))
    L += ["## 7. Limitations to state in the report", "",
          "- Few months, winter and early spring only; no summer or tourist-season data.",
          "- About ten hubs; rank correlations are unstable and many pairs are tested.",
          "- Taxi data covers yellow cabs only; Citi Bike covers docked stations only.",
          "- Weather effects are linear and descriptive; holidays and events are not modelled.", ""]
    return "\n".join(L)
