"""Day 6: join taxi, bike, retail (OSM) and weather data into analysis-ready hourly tables.

Two tables are built for one month:
  city panel : one row per hour (taxi pickups in Manhattan, bike starts near hubs, weather)
  hub panel  : one row per hub x hour (bike starts, static retail mix, weather)
"""
from __future__ import annotations

import calendar

import numpy as np
import pandas as pd


def hour_grid(year: int, month: int) -> pd.DatetimeIndex:
    n = calendar.monthrange(year, month)[1] * 24
    return pd.date_range(f"{year}-{month:02d}-01", periods=n, freq="h", name="datetime")


def taxi_hourly(trips: pd.DataFrame) -> pd.DataFrame:
    """Taxi pickups per hour. `trips` needs a tpep_pickup_datetime column."""
    s = trips["tpep_pickup_datetime"].dt.floor("h")
    out = s.value_counts().sort_index().rename("taxi_pickups").rename_axis("datetime")
    return out.reset_index()


def bike_hourly_by_hub(agg: pd.DataFrame, stations: pd.DataFrame) -> pd.DataFrame:
    """Citi Bike trip starts per hub per hour (only stations that belong to a hub)."""
    mapping = stations.loc[stations["hub_id"].notna(), ["station_id", "hub_id"]]
    a = agg.merge(mapping, left_on="start_station_id", right_on="station_id")
    a["datetime"] = pd.to_datetime(a["date"]) + pd.to_timedelta(a["hour"], unit="h")
    return (a.groupby(["hub_id", "datetime"])["trips"].sum()
            .rename("bike_starts").reset_index())


def taxi_hourly_by_hub(trips: pd.DataFrame, zone_map: pd.DataFrame) -> pd.DataFrame:
    """Taxi pickups per hub per hour, using the zone -> hub map from Day 8.

    `trips` needs tpep_pickup_datetime and PULocationID; `zone_map` needs LocationID and hub_id.
    Zones without a hub are ignored, so these counts cover the hub catchment zones only.
    """
    m = zone_map.loc[zone_map["hub_id"].notna(), ["LocationID", "hub_id"]]
    t = trips[["tpep_pickup_datetime", "PULocationID"]].merge(
        m, left_on="PULocationID", right_on="LocationID")
    t["datetime"] = t["tpep_pickup_datetime"].dt.floor("h")
    return (t.groupby(["hub_id", "datetime"]).size()
            .rename("taxi_pickups").reset_index())


def _time_features(df: pd.DataFrame) -> pd.DataFrame:
    df["date"] = df["datetime"].dt.date
    df["hour"] = df["datetime"].dt.hour
    df["day_of_week"] = df["datetime"].dt.dayofweek
    df["day_type"] = np.where(df["day_of_week"] >= 5, "weekend", "weekday")
    return df


def city_panel(taxi_h: pd.DataFrame, bike_hub_h: pd.DataFrame, weather: pd.DataFrame,
               year: int, month: int) -> pd.DataFrame:
    """One row per hour of the month. Missing counts become 0; weather is left-joined."""
    base = hour_grid(year, month).to_frame(index=False)
    bike_city = (bike_hub_h.groupby("datetime")["bike_starts"].sum()
                 .rename("bike_starts_hubs").reset_index())
    out = (base.merge(taxi_h, on="datetime", how="left")
               .merge(bike_city, on="datetime", how="left")
               .merge(weather, on="datetime", how="left"))
    out[["taxi_pickups", "bike_starts_hubs"]] = out[["taxi_pickups", "bike_starts_hubs"]].fillna(0).astype(int)
    return _time_features(out)


def hub_panel(bike_hub_h: pd.DataFrame, weather: pd.DataFrame, hubs, year: int, month: int,
              osm_summary: pd.DataFrame | None = None,
              taxi_hub_h: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per hub x hour (all combinations, zeros filled), with weather and retail mix.

    If `taxi_hub_h` (from taxi_hourly_by_hub) is given, a taxi_pickups column is added.
    """
    grid = hour_grid(year, month)
    idx = pd.MultiIndex.from_product([[h.hub_id for h in hubs], grid], names=["hub_id", "datetime"])
    out = idx.to_frame(index=False).merge(bike_hub_h, on=["hub_id", "datetime"], how="left")
    out["bike_starts"] = out["bike_starts"].fillna(0).astype(int)
    if taxi_hub_h is not None:
        out = out.merge(taxi_hub_h, on=["hub_id", "datetime"], how="left")
        out["taxi_pickups"] = out["taxi_pickups"].fillna(0).astype(int)
    out = out.merge(weather, on="datetime", how="left")
    meta = pd.DataFrame([{"hub_id": h.hub_id, "hub_name": h.name, "hub_type": h.type} for h in hubs])
    out = out.merge(meta, on="hub_id")
    if osm_summary is not None:
        keep = [c for c in osm_summary.columns if c not in ("hub_name", "hub_type", "radius_m")]
        osm = osm_summary[keep].rename(columns={"poi_total": "osm_poi_total",
                                                "poi_per_km2": "osm_poi_per_km2",
                                                "named_share": "osm_named_share"})
        out = out.merge(osm, on="hub_id", how="left")
    return _time_features(out)


def weather_effect(panel: pd.DataFrame, metrics: list[str], flag: str) -> pd.DataFrame:
    """% change in each metric in hours where `flag` is True, vs. comparable hours where it is False.

    'Comparable' = same hour-of-day and same day type (weekday/weekend), so the normal daily
    rhythm is not mistaken for a weather effect. Cells are weighted by their number of flagged hours.
    This is a descriptive comparison, not a causal estimate.
    """
    rows = []
    wet_n = panel[panel[flag]].groupby(["day_type", "hour"]).size().rename("n")
    for m in metrics:
        means = panel.groupby(["day_type", "hour", flag])[m].mean().unstack(flag)
        if True not in means.columns or False not in means.columns:
            rows.append({"flag": flag, "metric": m, "flagged_hours": int(panel[flag].sum()),
                         "other_hours": int((~panel[flag]).sum()), "change_pct": np.nan})
            continue
        cells = means.dropna(subset=[True, False]).join(wet_n, how="inner")
        cells = cells[cells[False] > 0]
        pct = ((cells["n"] * cells[True]).sum() / (cells["n"] * cells[False]).sum() - 1) * 100 if len(cells) else np.nan
        rows.append({"flag": flag, "metric": m, "flagged_hours": int(panel[flag].sum()),
                     "other_hours": int((~panel[flag]).sum()), "change_pct": round(float(pct), 1)})
    return pd.DataFrame(rows)


def daily_summary(city: pd.DataFrame) -> pd.DataFrame:
    """Daily totals and weather, handy for charts."""
    g = city.groupby("date")
    return pd.DataFrame({
        "taxi_pickups": g["taxi_pickups"].sum(),
        "bike_starts_hubs": g["bike_starts_hubs"].sum(),
        "precip_mm": g["precip_mm"].sum().round(1),
        "temp_mean_c": g["temp_c"].mean().round(1),
    }).reset_index()


def hub_mode_summary(hub: pd.DataFrame) -> pd.DataFrame:
    """Per hub: taxi vs bike volume, hourly correlation and weekday peak hours.

    taxi_share = taxi / (taxi + bike). Taxi counts cover the whole catchment zone(s) while bike
    counts cover docks within the hub radius, so treat the share as a relative mix indicator,
    not a measure of absolute market share.
    """
    if "taxi_pickups" not in hub.columns:
        raise ValueError("hub panel has no taxi_pickups column; build it with taxi_hub_h")
    rows = []
    for (hid, name, typ), g in hub.groupby(["hub_id", "hub_name", "hub_type"], sort=False):
        taxi, bike = int(g["taxi_pickups"].sum()), int(g["bike_starts"].sum())
        both_vary = g["taxi_pickups"].nunique() > 1 and g["bike_starts"].nunique() > 1
        wk = g[g["day_type"] == "weekday"].groupby("hour")
        rows.append({
            "hub_id": hid, "hub_name": name, "hub_type": typ,
            "taxi_pickups": taxi, "bike_starts": bike,
            "taxi_share": round(taxi / (taxi + bike), 3) if taxi + bike else np.nan,
            "hourly_corr_taxi_bike": round(float(g["taxi_pickups"].corr(g["bike_starts"])), 2) if both_vary else np.nan,
            "weekday_peak_hour_taxi": int(wk["taxi_pickups"].mean().idxmax()) if taxi else np.nan,
            "weekday_peak_hour_bike": int(wk["bike_starts"].mean().idxmax()) if bike else np.nan,
        })
    return pd.DataFrame(rows)
