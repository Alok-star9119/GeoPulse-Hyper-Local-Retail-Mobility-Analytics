"""Day 9: exploratory analysis of the daily and weekly rhythm of each retail hub.

Works on the hub panel (one row per hub x hour) and city panel built on Day 6 / Day 8.
Everything here is descriptive: it summarises *when* each hub is busy, it does not explain why.

Rhythm labels use simple rules with the thresholds below. They are heuristics for a one-month
sample; the numbers behind every label are always saved so thresholds can be reviewed.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

METRICS = ["taxi_pickups", "bike_starts"]

# Non-overlapping dayparts (hour ranges are inclusive)
DAYPARTS = {"night (0-5)": (0, 5), "morning (6-10)": (6, 10), "midday (11-15)": (11, 15),
            "afternoon (16-19)": (16, 19), "evening (20-23)": (20, 23)}
RUSH_HOURS = [7, 8, 9, 17, 18, 19]
MIDDAY_HOURS = [11, 12, 13, 14]
EVENING_HOURS = [20, 21, 22, 23]
DOW_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# Label thresholds (share of weekday volume; weekend_ratio = avg weekend day / avg weekday day)
COMMUTER_RUSH_SHARE = 0.30     # uniform volume would give 0.25 (6 of 24 hours)
COMMUTER_MAX_WEEKEND = 0.90
LEISURE_EVENING_SHARE = 0.20   # uniform volume would give 0.167 (4 of 24 hours)
LEISURE_MIN_WEEKEND = 1.00
MIDDAY_SHARE = 0.25            # uniform volume would give 0.167


def available_metrics(df: pd.DataFrame) -> list[str]:
    return [m for m in METRICS if m in df.columns]


# ---------- hourly rhythm ----------
def hourly_rhythm(hub: pd.DataFrame, metric: str) -> pd.DataFrame:
    """Average volume per hub x day type x hour, plus the share of that day type's daily volume."""
    g = (hub.groupby(["hub_id", "hub_name", "day_type", "hour"])[metric].mean()
         .rename("avg").reset_index())
    tot = g.groupby(["hub_id", "day_type"])["avg"].transform("sum")
    g["share"] = np.where(tot > 0, g["avg"] / tot.replace(0, np.nan), np.nan)
    g["avg"] = g["avg"].round(3)
    g["share"] = g["share"].round(4)
    g.insert(0, "metric", metric)
    return g


def weekly_heatmap(df: pd.DataFrame, metric: str) -> pd.DataFrame:
    """7 x 24 table (Mon..Sun by hour) of average volume. Works on the city or one hub's rows."""
    h = df.groupby(["day_of_week", "hour"])[metric].mean().unstack("hour")
    h = h.reindex(index=range(7), columns=range(24))
    h.index = DOW_NAMES
    return h.round(2)


# ---------- per-hub statistics ----------
def _share(profile: pd.Series, hours) -> float:
    total = profile.sum()
    return float(profile.reindex(list(hours)).fillna(0).sum() / total) if total > 0 else np.nan


def daypart_shares(profile: pd.Series) -> dict:
    """Share of a 24-hour profile falling in each non-overlapping daypart."""
    return {name: _share(profile, range(lo, hi + 1)) for name, (lo, hi) in DAYPARTS.items()}


def weekend_ratio(hub_rows: pd.DataFrame, metric: str) -> float:
    """Average weekend-day total divided by average weekday-day total (1.0 = no difference)."""
    daily = hub_rows.groupby(["date", "day_type"])[metric].sum().reset_index()
    means = daily.groupby("day_type")[metric].mean()
    if "weekday" not in means or "weekend" not in means or means["weekday"] == 0:
        return np.nan
    return float(means["weekend"] / means["weekday"])


def classify_rhythm(rush_share, evening_share, midday_share, wk_ratio) -> str:
    """Rule-based label. Order matters: commuter, leisure, midday, otherwise mixed."""
    if any(pd.isna(x) for x in (rush_share, evening_share, midday_share)):
        return "no data"
    if rush_share >= COMMUTER_RUSH_SHARE and (pd.isna(wk_ratio) or wk_ratio < COMMUTER_MAX_WEEKEND):
        return "commuter"
    if evening_share >= LEISURE_EVENING_SHARE and (not pd.isna(wk_ratio)) and wk_ratio >= LEISURE_MIN_WEEKEND:
        return "leisure / evening"
    if midday_share >= MIDDAY_SHARE:
        return "midday / shopping"
    return "all-day mixed"


def hub_rhythm_stats(hub: pd.DataFrame, metric: str) -> pd.DataFrame:
    """One row per hub: peaks, concentration, dayparts, weekend ratio and a rhythm label."""
    rows = []
    for (hid, name, typ), g in hub.groupby(["hub_id", "hub_name", "hub_type"], sort=False):
        total = int(g[metric].sum())
        prof = {dt: g[g["day_type"] == dt].groupby("hour")[metric].mean().reindex(range(24), fill_value=0)
                for dt in ("weekday", "weekend")}
        wk = prof["weekday"]
        row = {"metric": metric, "hub_id": hid, "hub_name": name, "hub_type": typ, "total": total}
        if total == 0:
            row.update({"rhythm": "no data"})
            rows.append(row)
            continue
        ratio = weekend_ratio(g, metric)
        rush, midday, evening = _share(wk, RUSH_HOURS), _share(wk, MIDDAY_HOURS), _share(wk, EVENING_HOURS)
        row.update({
            "weekday_peak_hour": int(wk.idxmax()),
            "weekend_peak_hour": int(prof["weekend"].idxmax()) if prof["weekend"].sum() > 0 else np.nan,
            "peak_to_mean": round(float(wk.max() / wk.mean()), 2) if wk.mean() > 0 else np.nan,
            "rush_share": round(rush, 3), "midday_share": round(midday, 3),
            "evening_share": round(evening, 3),
            "weekend_ratio": round(ratio, 2) if not pd.isna(ratio) else np.nan,
            **{f"share_{k.split(' ')[0]}": round(v, 3) for k, v in daypart_shares(wk).items()},
            "rhythm": classify_rhythm(rush, evening, midday, ratio),
        })
        rows.append(row)
    return pd.DataFrame(rows)


def profile_similarity(rhythm: pd.DataFrame, day_type: str = "weekday") -> pd.DataFrame:
    """Hub x hub correlation of normalised hourly profiles (input: output of hourly_rhythm).

    A hub whose profile is perfectly flat has no variation, so its correlations are NaN."""
    r = rhythm[rhythm["day_type"] == day_type].pivot(index="hour", columns="hub_name", values="share")
    return r.dropna(axis=1, how="all").corr().round(2)


# ---------- unusual days ----------
def daily_extremes(city: pd.DataFrame, metric: str, k: int = 3) -> pd.DataFrame:
    """Busiest and quietest days with their weather, to explain outliers."""
    d = (city.groupby("date")
         .agg(total=(metric, "sum"), precip_mm=("precip_mm", "sum"), temp_mean_c=("temp_c", "mean"),
              day_of_week=("day_of_week", "first")).reset_index())
    d["weekday"] = d["day_of_week"].map(dict(enumerate(DOW_NAMES)))
    d["temp_mean_c"] = d["temp_mean_c"].round(1)
    d["precip_mm"] = d["precip_mm"].round(1)
    top = d.nlargest(k, "total").assign(kind="busiest")
    low = d.nsmallest(k, "total").assign(kind="quietest")
    out = pd.concat([top, low], ignore_index=True)
    out.insert(0, "metric", metric)
    return out[["metric", "kind", "date", "weekday", "total", "precip_mm", "temp_mean_c"]]


# ---------- report ----------
def render_report(stats: pd.DataFrame, extremes: pd.DataFrame, ym: str) -> str:
    L = [f"# Day 9: Hub Rhythm EDA ({ym})", "",
         "Generated by `scripts/eda_hub_rhythm.py`. Descriptive only: one month of data, so patterns are indicative.", "",
         "## How labels are assigned",
         f"- **commuter**: >= {COMMUTER_RUSH_SHARE:.0%} of weekday volume in rush hours (07-09, 17-19) and weekends below {COMMUTER_MAX_WEEKEND:.0%} of weekdays",
         f"- **leisure / evening**: >= {LEISURE_EVENING_SHARE:.0%} of weekday volume at 20-23 h and weekends at least as busy as weekdays",
         f"- **midday / shopping**: >= {MIDDAY_SHARE:.0%} of weekday volume at 11-14 h",
         "- **all-day mixed**: none of the above; **no data**: no trips in the hub catchment", ""]
    for metric, g in stats.groupby("metric", sort=False):
        L += [f"## {metric.replace('_', ' ').title()} by hub", "",
              "| Hub | Type | Total | Weekday peak | Weekend peak | Peak/mean | Rush share | Weekend ratio | Rhythm |",
              "|---|---|---|---|---|---|---|---|---|"]
        for r in g.itertuples():
            f = lambda v, fmt="{}": "-" if pd.isna(v) else fmt.format(v)
            L.append(f"| {r.hub_name} | {r.hub_type} | {r.total:,} | {f(getattr(r, 'weekday_peak_hour', np.nan), '{:.0f}:00')} | "
                     f"{f(getattr(r, 'weekend_peak_hour', np.nan), '{:.0f}:00')} | {f(getattr(r, 'peak_to_mean', np.nan))} | "
                     f"{f(getattr(r, 'rush_share', np.nan), '{:.0%}')} | {f(getattr(r, 'weekend_ratio', np.nan))} | {r.rhythm} |")
        L.append("")
    L += ["## Busiest and quietest days (city level)", "",
          "| Metric | Kind | Date | Day | Total | Precip (mm) | Mean temp (C) |", "|---|---|---|---|---|---|---|"]
    for e in extremes.itertuples():
        L.append(f"| {e.metric} | {e.kind} | {e.date} | {e.weekday} | {e.total:,} | {e.precip_mm} | {e.temp_mean_c} |")
    L += ["", "## Reading the results",
          "- Peak/mean above ~2 means volume is concentrated in a few hours; near 1 means evenly spread.",
          "- Weekend ratio above 1 means a typical weekend day is busier than a weekday.",
          "- Holidays, storms and events can explain extreme days; check the weather columns before drawing conclusions.", ""]
    return "\n".join(L)
