"""Day 7: automated data-quality checks for the combined hourly tables.

Each check returns a dict: {check, scope, status, detail} with status in
pass / warn / fail / skip. Checks never modify data.
"""
from __future__ import annotations

import calendar

import numpy as np
import pandas as pd

CITY_REQUIRED = ["datetime", "taxi_pickups", "bike_starts_hubs", "temp_c", "precip_mm",
                 "wind_kmh", "is_wet", "is_cold", "date", "hour", "day_type"]
HUB_REQUIRED = ["hub_id", "datetime", "bike_starts", "temp_c", "precip_mm", "hub_name", "hour", "day_type"]

TEMP_RANGE = (-40.0, 45.0)      # C, plausible for New York
MAX_PRECIP_MM_HOUR = 100.0
MAX_WIND_KMH = 200.0
DAYTIME = range(7, 23)          # hours 07:00-22:59 should never be empty
OUTLIER_Z = 3.5
OUTLIER_WARN_SHARE = 0.02
REMOVED_WARN, REMOVED_FAIL = 0.10, 0.30
SOURCES_USED = ["tlc_trips", "tlc_zone_lookup", "citibike_trips", "osm_pois", "open_meteo"]


def _r(check: str, scope: str, status: str, detail: str) -> dict:
    return {"check": check, "scope": scope, "status": status, "detail": detail}


def expected_hours(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1] * 24


# ---------- structure ----------
def check_schema(df: pd.DataFrame, required: list[str], scope: str) -> dict:
    missing = [c for c in required if c not in df.columns]
    if missing:
        return _r("schema", scope, "fail", f"missing columns: {missing}")
    return _r("schema", scope, "pass", f"all {len(required)} required columns present")


def check_row_count(df: pd.DataFrame, expected: int, scope: str) -> dict:
    if len(df) == expected:
        return _r("row_count", scope, "pass", f"{len(df)} rows as expected")
    return _r("row_count", scope, "fail", f"{len(df)} rows, expected {expected}")


def check_unique(df: pd.DataFrame, keys: list[str], scope: str) -> dict:
    dup = int(df.duplicated(subset=keys).sum())
    if dup == 0:
        return _r("unique_key", scope, "pass", f"no duplicate {keys}")
    return _r("unique_key", scope, "fail", f"{dup} duplicate rows on {keys}")


# ---------- values ----------
def check_no_negative(df: pd.DataFrame, cols: list[str], scope: str) -> dict:
    bad = {c: int((df[c] < 0).sum()) for c in cols if c in df.columns and (df[c] < 0).any()}
    if bad:
        return _r("no_negative_counts", scope, "fail", f"negative values: {bad}")
    return _r("no_negative_counts", scope, "pass", f"{cols} are all >= 0")


def check_nulls(df: pd.DataFrame, cols: list[str], scope: str) -> dict:
    bad = {c: int(df[c].isna().sum()) for c in cols if c in df.columns and df[c].isna().any()}
    if bad:
        return _r("no_nulls", scope, "fail", f"null counts: {bad}")
    return _r("no_nulls", scope, "pass", f"no nulls in {len(cols)} key columns")


def check_weather_ranges(df: pd.DataFrame, scope: str) -> dict:
    problems = []
    if not df["temp_c"].between(*TEMP_RANGE).all():
        problems.append(f"temp outside {TEMP_RANGE}")
    if not df["precip_mm"].between(0, MAX_PRECIP_MM_HOUR).all():
        problems.append(f"precip outside 0-{MAX_PRECIP_MM_HOUR} mm/h")
    if not df["wind_kmh"].between(0, MAX_WIND_KMH).all():
        problems.append(f"wind outside 0-{MAX_WIND_KMH} km/h")
    if not df["hour"].between(0, 23).all():
        problems.append("hour outside 0-23")
    if problems:
        return _r("weather_ranges", scope, "fail", "; ".join(problems))
    return _r("weather_ranges", scope, "pass",
              f"temp {df['temp_c'].min():.1f} to {df['temp_c'].max():.1f} C, "
              f"precip max {df['precip_mm'].max():.1f} mm/h, wind max {df['wind_kmh'].max():.0f} km/h")


def check_daytime_gaps(city: pd.DataFrame, cols: list[str], scope: str) -> dict:
    """Zero trips in a daytime hour usually means missing data, not a quiet city."""
    day = city[city["hour"].isin(DAYTIME)]
    gaps = {c: int((day[c] == 0).sum()) for c in cols if (day[c] == 0).any()}
    if gaps:
        return _r("daytime_gaps", scope, "warn", f"hours (07-22) with zero trips: {gaps}")
    return _r("daytime_gaps", scope, "pass", "no empty daytime hours")


# ---------- consistency between tables ----------
def check_hub_matches_city(hub: pd.DataFrame, city: pd.DataFrame) -> dict:
    h = hub.groupby("datetime")["bike_starts"].sum()
    c = city.set_index("datetime")["bike_starts_hubs"]
    joined = pd.concat([h, c], axis=1, keys=["hub", "city"]).fillna(0)
    diff = int((joined["hub"] != joined["city"]).sum())
    if diff == 0:
        return _r("hub_sum_equals_city", "hub vs city", "pass",
                  f"hub bike starts add up to the city total in all {len(joined)} hours")
    return _r("hub_sum_equals_city", "hub vs city", "fail", f"{diff} hours differ")


def check_static_columns(hub: pd.DataFrame, cols: list[str]) -> dict:
    present = [c for c in cols if c in hub.columns]
    if not present:
        return _r("retail_columns_constant", "hub panel", "skip", "no OSM columns (run ingest_osm.py first)")
    varying = [c for c in present if (hub.groupby("hub_id")[c].nunique(dropna=False) > 1).any()]
    if varying:
        return _r("retail_columns_constant", "hub panel", "fail", f"values change within a hub: {varying}")
    return _r("retail_columns_constant", "hub panel", "pass", "static retail columns are constant per hub")


def check_hubs_without_bikes(hub: pd.DataFrame) -> dict:
    tot = hub.groupby("hub_name")["bike_starts"].sum()
    empty = sorted(tot[tot == 0].index)
    if empty:
        return _r("hubs_without_bike_data", "hub panel", "warn",
                  f"{len(empty)} hub(s) have no Citi Bike stations nearby: {empty}")
    return _r("hubs_without_bike_data", "hub panel", "pass", "every hub has bike data")


# ---------- outliers ----------
def flag_outliers(city: pd.DataFrame, metric: str, z: float = OUTLIER_Z) -> pd.DataFrame:
    """Hours that are unusual for their hour-of-day and day type (robust z-score using median/MAD)."""
    g = city.groupby(["day_type", "hour"])[metric]
    med = g.transform("median")
    mad = (city[metric] - med).abs().groupby([city["day_type"], city["hour"]]).transform("median")
    mad = mad.replace(0, np.nan)
    rz = 0.6745 * (city[metric] - med) / mad
    out = city.assign(metric=metric, value=city[metric], expected=med, robust_z=rz.round(2))
    out = out[rz.abs() > z]
    cols = ["datetime", "metric", "value", "expected", "robust_z", "is_wet", "is_cold"]
    return out[cols].reset_index(drop=True)


def check_outliers(city: pd.DataFrame, metrics: list[str]) -> tuple[dict, pd.DataFrame]:
    frames = [flag_outliers(city, m) for m in metrics]
    anomalies = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    anomalies = anomalies.reindex(anomalies["robust_z"].abs().sort_values(ascending=False).index) \
        if len(anomalies) else anomalies
    n_obs = len(city) * len(metrics)
    share = len(anomalies) / n_obs if n_obs else 0
    wet = int(anomalies["is_wet"].sum()) if len(anomalies) else 0
    detail = (f"{len(anomalies)} unusual hour-values of {n_obs} ({share:.1%}); "
              f"{wet} fall in wet hours (see weather).")
    status = "warn" if share > OUTLIER_WARN_SHARE else "pass"
    return _r("outlier_hours", "city panel", status, detail), anomalies.reset_index(drop=True)


# ---------- upstream cleaning / catalog ----------
def check_removed_share(report: dict | None, name: str, rows_key: str, kept_key: str) -> dict:
    if not report:
        return _r("rows_removed_by_cleaning", name, "skip", "quality report not found")
    rows, kept = report.get(rows_key), report.get(kept_key)
    if not rows:
        return _r("rows_removed_by_cleaning", name, "skip", "no row counts in report")
    share = 1 - kept / rows
    status = "fail" if share > REMOVED_FAIL else "warn" if share > REMOVED_WARN else "pass"
    return _r("rows_removed_by_cleaning", name, status, f"{share:.1%} of {rows:,} rows removed by cleaning")


def check_catalog_verified(catalog: pd.DataFrame) -> dict:
    sub = catalog[catalog["source_id"].isin(SOURCES_USED)]
    not_ok = sorted(sub.loc[sub["status"] != "verified", "source_id"])
    missing = sorted(set(SOURCES_USED) - set(sub["source_id"]))
    if missing or not_ok:
        return _r("sources_verified", "catalog", "warn",
                  f"not verified: {not_ok}; not in catalog: {missing}")
    return _r("sources_verified", "catalog", "pass", f"all {len(SOURCES_USED)} sources used are verified")


# ---------- run everything ----------
def run_all(city: pd.DataFrame, hub: pd.DataFrame, year: int, month: int, hubs_count: int = 10,
            catalog: pd.DataFrame | None = None, tlc_report: dict | None = None,
            bike_report: dict | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    n = expected_hours(year, month)
    res = [
        check_schema(city, CITY_REQUIRED, "city panel"),
        check_row_count(city, n, "city panel"),
        check_unique(city, ["datetime"], "city panel"),
        check_nulls(city, ["taxi_pickups", "bike_starts_hubs", "temp_c", "precip_mm", "wind_kmh"], "city panel"),
        check_no_negative(city, ["taxi_pickups", "bike_starts_hubs", "precip_mm"], "city panel"),
        check_weather_ranges(city, "city panel"),
        check_daytime_gaps(city, ["taxi_pickups", "bike_starts_hubs"], "city panel"),
        check_schema(hub, HUB_REQUIRED, "hub panel"),
        check_row_count(hub, n * hubs_count, "hub panel"),
        check_unique(hub, ["hub_id", "datetime"], "hub panel"),
        check_no_negative(hub, ["bike_starts"], "hub panel"),
        check_hub_matches_city(hub, city),
        check_static_columns(hub, ["osm_poi_total", "osm_poi_per_km2", "osm_named_share"]),
        check_hubs_without_bikes(hub),
    ]
    out_check, anomalies = check_outliers(city, ["taxi_pickups", "bike_starts_hubs"])
    res.append(out_check)
    res.append(check_removed_share(tlc_report, "taxi (Day 3)", "rows", "rows_after_clean"))
    res.append(check_removed_share(bike_report, "bikes (Day 5)", "rows_read", "rows_kept"))
    if catalog is not None:
        res.append(check_catalog_verified(catalog))
    return pd.DataFrame(res), anomalies


# ---------- report ----------
def render_report(results: pd.DataFrame, anomalies: pd.DataFrame, lineage: pd.DataFrame, ym: str) -> str:
    counts = results["status"].value_counts().to_dict()
    icon = {"pass": "PASS", "warn": "WARN", "fail": "FAIL", "skip": "SKIP"}
    lines = [f"# Week 1 Data Quality Report ({ym})", "",
             "Generated by `scripts/quality_review.py`. Re-run it after any data change.", "",
             "## Summary",
             f"- PASS {counts.get('pass', 0)} | WARN {counts.get('warn', 0)} | "
             f"FAIL {counts.get('fail', 0)} | SKIP {counts.get('skip', 0)}", "",
             "## Checks", "", "| Status | Check | Scope | Detail |", "|---|---|---|---|"]
    for r in results.itertuples():
        lines.append(f"| {icon[r.status]} | {r.check} | {r.scope} | {r.detail} |")
    lines += ["", "## Most unusual hours", ""]
    if len(anomalies):
        lines += ["Hours that differ strongly from the usual value for their hour-of-day and day type.",
                  "Holidays, storms and events are expected here; they are flagged, not removed.", "",
                  "| Datetime | Metric | Value | Expected | Robust z | Wet hour |", "|---|---|---|---|---|---|"]
        for a in anomalies.head(10).itertuples():
            lines.append(f"| {a.datetime} | {a.metric} | {a.value:.0f} | {a.expected:.0f} | {a.robust_z} | {a.is_wet} |")
    else:
        lines.append("None found.")
    lines += ["", "## Data lineage (files for this month)", "", "| File | Rows |", "|---|---|"]
    for f in lineage.itertuples():
        lines.append(f"| {f.file} | {f.rows} |")
    lines += ["", "## Decisions", "",
              "- Outlier hours are **flagged, not deleted**: they may be real (holidays, storms).",
              "- Hubs without Citi Bike stations stay in the data with zero bike starts; this is a coverage gap, not an error.",
              "- Any FAIL must be fixed before Week 2 analysis; WARN items must be explained in the findings.", ""]
    return "\n".join(lines)
