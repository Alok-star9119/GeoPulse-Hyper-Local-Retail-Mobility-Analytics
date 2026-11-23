"""Day 14: collect headline numbers from the per-month tables into one short, checkable summary.

Nothing is computed twice: every number is read from a committed table written by an earlier day,
so the summary can be regenerated whenever new months are added.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from geopulse import multimonth as mm


def _read(tables: Path, template: str, ym: str) -> pd.DataFrame | None:
    f = Path(tables) / template.format(ym=ym)
    return pd.read_csv(f) if f.exists() else None


def quality_summary(tables: Path, months: list[str]) -> pd.DataFrame:
    rows = []
    for ym in months:
        q = _read(tables, "quality_checks_{ym}.csv", ym)
        if q is None:
            continue
        c = q["status"].value_counts()
        rows.append({"month": ym, "checks": len(q), "pass": int(c.get("pass", 0)), "warn": int(c.get("warn", 0)),
                     "fail": int(c.get("fail", 0))})
    return pd.DataFrame(rows, columns=["month", "checks", "pass", "warn", "fail"])


def forecast_summary(tables: Path, months: list[str]) -> pd.DataFrame:
    """WAPE of each model per month and target, plus how many points weather removed."""
    rows = []
    for ym in months:
        f = _read(tables, "forecast_metrics_{ym}.csv", ym)
        if f is None:
            continue
        for t, g in f.groupby("target", sort=False):
            w = g.set_index("model")["wape_pct"]
            rows.append({"month": ym, "target": t, "wape_naive": w.get("seasonal_naive"), "wape_hour_of_week": w.get("hour_of_week"),
                         "wape_with_weather": w.get("hour_of_week_weather"),
                         "weather_gain_pts": round(float(w.get("hour_of_week") - w.get("hour_of_week_weather")), 1)})
    return pd.DataFrame(rows, columns=["month", "target", "wape_naive", "wape_hour_of_week", "wape_with_weather", "weather_gain_pts"])


def stability_summary(tables: Path, months: list[str]) -> dict:
    """Counts from the Day 11 comparison; empty when fewer than 2 months exist."""
    if len(months) < 2:
        return {}
    stats, _ = mm.stack(tables, "hub_rhythm_stats_{ym}.csv", months)
    corr, _ = mm.stack(tables, "retail_mobility_correlations_{ym}.csv", months)
    out = {}
    if len(stats):
        lab = mm.label_stability(stats)
        multi = lab[lab["n_months"] >= 2]
        out["labels_stable"], out["labels_total"] = int(multi["stable"].sum()), len(multi)
    cons = mm.correlation_consistency(corr)
    if len(cons):
        multi = cons[cons["n_months"] >= 2]
        out["corr_consistent"], out["corr_total"] = int(multi["consistent"].sum()), len(multi)
    return out


def render(months: list[str], quality: pd.DataFrame, forecast: pd.DataFrame, stability: dict, root: Path) -> str:
    L = ["# Key Numbers (generated)", "",
         f"Months with a panel: {', '.join(months) if months else 'none'}. Every figure below is read from a table in `reports/tables/`.", "",
         "## Data quality (Day 7 checks)", ""]
    if len(quality):
        L += ["| Month | Checks | Pass | Warn | Fail |", "|---|---|---|---|---|"]
        L += [f"| {r.month} | {r.checks} | {r.pass_} | {r.warn} | {r.fail} |" for r in quality.rename(columns={"pass": "pass_"}).itertuples()]
    else:
        L.append("No quality tables found. Run `python scripts/quality_review.py`.")
    L += ["", "## Forecast accuracy (Day 13, WAPE % on the last 7 days, lower is better)", ""]
    if len(forecast):
        L += ["| Month | Target | Seasonal naive | Hour-of-week | With weather | Weather gain (pts) |", "|---|---|---|---|---|---|"]
        L += [f"| {r.month} | {r.target} | {r.wape_naive} | {r.wape_hour_of_week} | {r.wape_with_weather} | {r.weather_gain_pts} |" for r in forecast.itertuples()]
    else:
        L.append("No forecast tables found. Run `python scripts/forecast_baseline.py`.")
    L += ["", "## Stability across months (Day 11)", ""]
    if stability:
        if "labels_total" in stability:
            L.append(f"- Rhythm labels unchanged in every month: {stability['labels_stable']} of {stability['labels_total']} hub-metric pairs.")
        if "corr_total" in stability:
            L.append(f"- Retail-mobility correlations with the same sign and |rho| >= {mm.MIN_ABS_RHO} in every month: "
                     f"{stability['corr_consistent']} of {stability['corr_total']}.")
    else:
        L.append("Needs at least 2 months. Run `python scripts/run_months.py --months 2024-02 2024-03`.")
    present = [p for p in ("reports/dashboard.html", "reports/day11_multi_month_comparison.md") if (Path(root) / p).exists()]
    L += ["", "## Deliverables present", ""] + ([f"- `{p}`" for p in present] or ["- none of the generated reports found yet"]) + [""]
    return "\n".join(L)
