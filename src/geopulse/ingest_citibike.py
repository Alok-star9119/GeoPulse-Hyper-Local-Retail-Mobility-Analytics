"""Day 5: ingest Citi Bike trips, summarise them by station and retail hub.

Citi Bike trip files are large (millions of rows per month), so they are read in chunks and
reduced to small aggregates (station x date x hour x user type) as they stream in.
Data: Citi Bike System Data, see https://citibikenyc.com/system-data (check licence/attribution).
"""
from __future__ import annotations

import calendar
import io
import zipfile
from pathlib import Path
from typing import Iterator

import numpy as np
import pandas as pd

from geopulse.config import RAW_DIR
from geopulse.download import download_file
from geopulse.geo import haversine_m_array
from geopulse.logger import get_logger

log = get_logger(__name__)

CITIBIKE_RAW_DIR = RAW_DIR / "citibike"
BASE_URL = "https://s3.amazonaws.com/tripdata/"

# Needed columns (new schema, 2021+). Older files use different names, see RENAME_OLD.
TRIP_COLUMNS = ["started_at", "ended_at", "start_station_id", "start_station_name",
                "start_lat", "start_lng", "member_casual"]
RENAME_OLD = {"starttime": "started_at", "stoptime": "ended_at",
              "start station id": "start_station_id", "start station name": "start_station_name",
              "start station latitude": "start_lat", "start station longitude": "start_lng",
              "usertype": "member_casual"}
USER_MAP = {"Subscriber": "member", "Customer": "casual", "member": "member", "casual": "casual"}

MIN_TRIP_SECONDS = 60       # shorter trips are usually false starts / re-docks
MAX_TRIP_HOURS = 24


# ---------- download / read ----------
def candidate_urls(year: int, month: int) -> list[str]:
    """File-name patterns seen on the Citi Bike bucket. Tried in order (verify on first run)."""
    ym = f"{year}{month:02d}"
    return [f"{BASE_URL}{ym}-citibike-tripdata.csv.zip",
            f"{BASE_URL}{ym}-citibike-tripdata.zip"]


def download_month(year: int, month: int, url: str | None = None) -> Path:
    """Download one monthly file. Uses `url` if given, else tries the known patterns."""
    urls = [url] if url else candidate_urls(year, month)
    last: Exception | None = None
    for u in urls:
        dest = CITIBIKE_RAW_DIR / Path(u).name
        try:
            return download_file(u, dest, retries=2)
        except RuntimeError as err:
            last = err
            log.warning("Could not fetch %s", u)
    raise RuntimeError(f"No Citi Bike file found for {year}-{month:02d}. "
                       "Open https://s3.amazonaws.com/tripdata/index.html, copy the file link "
                       "and pass it with --url, or download it by hand and pass --file.") from last


def _csv_sources(path: Path) -> Iterator[tuple[str, io.BufferedIOBase]]:
    """Yield (name, binary file object) for every CSV in a .zip (or the .csv itself)."""
    path = Path(path)
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as zf:
            for name in sorted(zf.namelist()):
                if name.lower().endswith(".csv") and "__MACOSX" not in name:
                    with zf.open(name) as fh:
                        yield name, fh
    else:
        with open(path, "rb") as fh:
            yield path.name, fh


def iter_trip_chunks(path: Path, chunksize: int = 500_000) -> Iterator[pd.DataFrame]:
    """Stream trips from a zip/csv as DataFrames with the standard column names."""
    for name, fh in _csv_sources(path):
        log.info("Reading %s", name)
        header = pd.read_csv(fh, nrows=0).columns
        fh.seek(0) if fh.seekable() else None
        cols = [c for c in header if c in TRIP_COLUMNS or c in RENAME_OLD]
        for chunk in pd.read_csv(fh, usecols=cols, chunksize=chunksize,
                                 dtype={"start_station_id": str, "start station id": str},
                                 low_memory=False):
            chunk = chunk.rename(columns=RENAME_OLD)
            missing = [c for c in TRIP_COLUMNS if c not in chunk.columns]
            if missing:
                raise ValueError(f"{name}: missing columns {missing}")
            yield chunk[TRIP_COLUMNS]


# ---------- clean / aggregate ----------
def clean_chunk(df: pd.DataFrame, bbox: dict, year: int, month: int) -> pd.DataFrame:
    """Parse times, drop invalid rows, keep trips that START inside the study area and month."""
    d = df.copy()
    d["started_at"] = pd.to_datetime(d["started_at"], errors="coerce")
    d["ended_at"] = pd.to_datetime(d["ended_at"], errors="coerce")
    d["start_lat"] = pd.to_numeric(d["start_lat"], errors="coerce")
    d["start_lng"] = pd.to_numeric(d["start_lng"], errors="coerce")
    secs = (d["ended_at"] - d["started_at"]).dt.total_seconds()
    keep = (
        d["started_at"].notna() & d["ended_at"].notna()
        & (d["started_at"].dt.year == year) & (d["started_at"].dt.month == month)
        & (secs >= MIN_TRIP_SECONDS) & (secs <= MAX_TRIP_HOURS * 3600)
        & d["start_station_id"].notna()
        & d["start_lat"].between(bbox["min_lat"], bbox["max_lat"])
        & d["start_lng"].between(bbox["min_lon"], bbox["max_lon"])
    )
    out = d.loc[keep].copy()
    out["user_type"] = out["member_casual"].map(USER_MAP).fillna("unknown")
    return out


def aggregate_chunk(df: pd.DataFrame) -> pd.DataFrame:
    """Reduce cleaned trips to station x date x hour x user_type counts (+ coordinate sums)."""
    g = df.assign(date=df["started_at"].dt.date, hour=df["started_at"].dt.hour)
    return (g.groupby(["start_station_id", "start_station_name", "date", "hour", "user_type"],
                      dropna=False)
             .agg(trips=("started_at", "size"), lat_sum=("start_lat", "sum"),
                  lng_sum=("start_lng", "sum"))
             .reset_index())


def combine_aggregates(parts: list[pd.DataFrame]) -> pd.DataFrame:
    """Merge per-chunk aggregates (the same key can appear in several chunks)."""
    if not parts:
        raise ValueError("No data after cleaning")
    allp = pd.concat(parts, ignore_index=True)
    keys = ["start_station_id", "start_station_name", "date", "hour", "user_type"]
    return allp.groupby(keys, dropna=False)[["trips", "lat_sum", "lng_sum"]].sum().reset_index()


def process_file(path: Path, bbox: dict, year: int, month: int,
                 chunksize: int = 500_000) -> tuple[pd.DataFrame, dict]:
    """Stream a file, returning (aggregates, row-count report)."""
    parts, rows_in, rows_kept = [], 0, 0
    for chunk in iter_trip_chunks(path, chunksize):
        rows_in += len(chunk)
        clean = clean_chunk(chunk, bbox, year, month)
        rows_kept += len(clean)
        if len(clean):
            parts.append(aggregate_chunk(clean))
    report = {"year": year, "month": month, "rows_read": rows_in, "rows_kept": rows_kept,
              "rows_removed": rows_in - rows_kept,
              "removed_share": round((rows_in - rows_kept) / rows_in, 4) if rows_in else None}
    return combine_aggregates(parts), report


# ---------- station / hub analysis ----------
def station_table(agg: pd.DataFrame) -> pd.DataFrame:
    """One row per station: location, trips, casual share."""
    g = agg.groupby("start_station_id")
    st = pd.DataFrame({
        "station_name": g["start_station_name"].agg(lambda s: s.mode().iloc[0] if s.notna().any() else None),
        "trips": g["trips"].sum(),
        "lat": g["lat_sum"].sum() / g["trips"].sum(),
        "lon": g["lng_sum"].sum() / g["trips"].sum(),
    })
    casual = agg[agg["user_type"] == "casual"].groupby("start_station_id")["trips"].sum()
    st["casual_share"] = (casual.reindex(st.index).fillna(0) / st["trips"]).round(3)
    st["lat"], st["lon"] = st["lat"].round(6), st["lon"].round(6)
    return st.reset_index().rename(columns={"start_station_id": "station_id"})


def assign_hubs(stations: pd.DataFrame, hubs, radius_m: float = 500) -> pd.DataFrame:
    """Add nearest_hub_id, nearest_hub_m and hub_id (nearest hub if within radius, else None)."""
    dists = pd.DataFrame({h.hub_id: haversine_m_array(stations.lat, stations.lon, h.lat, h.lon)
                          for h in hubs})
    out = stations.copy()
    out["nearest_hub_id"] = dists.idxmin(axis=1).values
    out["nearest_hub_m"] = dists.min(axis=1).round(1).values
    out["hub_id"] = np.where(out["nearest_hub_m"] <= radius_m, out["nearest_hub_id"], None)
    return out


def calendar_day_counts(year: int, month: int) -> dict:
    """Number of weekdays and weekend days in a month."""
    n = calendar.monthrange(year, month)[1]
    days = pd.date_range(f"{year}-{month:02d}-01", periods=n)
    wk = int((days.dayofweek >= 5).sum())
    return {"weekday": n - wk, "weekend": wk}


def add_day_type(agg: pd.DataFrame) -> pd.DataFrame:
    out = agg.copy()
    dow = pd.to_datetime(out["date"]).dt.dayofweek
    out["day_type"] = np.where(dow >= 5, "weekend", "weekday")
    return out


def hub_hourly_profile(agg: pd.DataFrame, stations: pd.DataFrame, year: int, month: int) -> pd.DataFrame:
    """Average bike trip starts per hour near each hub (stations within the hub radius)."""
    mapping = stations.loc[stations["hub_id"].notna(), ["station_id", "hub_id"]]
    a = add_day_type(agg).merge(mapping, left_on="start_station_id", right_on="station_id")
    prof = (a.groupby(["hub_id", "day_type", "hour"])["trips"].sum()
            .rename("trips_total").reset_index())
    days = calendar_day_counts(year, month)
    prof["days"] = prof["day_type"].map(days)
    prof["avg_trips"] = (prof["trips_total"] / prof["days"]).round(2)
    return prof


def hub_summary(stations: pd.DataFrame, profile: pd.DataFrame, hubs, radius_m: float = 500) -> pd.DataFrame:
    """Per hub: stations nearby, trips, casual share, weekday peak hour."""
    rows = []
    for h in hubs:
        s = stations[stations["hub_id"] == h.hub_id]
        p = profile[(profile["hub_id"] == h.hub_id) & (profile["day_type"] == "weekday")]
        peak = int(p.loc[p["avg_trips"].idxmax(), "hour"]) if len(p) else None
        trips = int(s["trips"].sum())
        casual = float((s["casual_share"] * s["trips"]).sum() / trips) if trips else None
        rows.append({"hub_id": h.hub_id, "hub_name": h.name, "hub_type": h.type,
                     "radius_m": radius_m, "stations": len(s), "trips": trips,
                     "casual_share": round(casual, 3) if casual is not None else None,
                     "weekday_peak_hour": peak})
    return pd.DataFrame(rows)


# ---------- compare with taxi (Day 3) ----------
def normalised_hourly(df: pd.DataFrame, value: str, day_type: str = "weekday") -> pd.Series:
    """Share of the day's total in each hour (sums to 1), for one day type."""
    s = df[df["day_type"] == day_type].groupby("hour")[value].sum().reindex(range(24), fill_value=0)
    return s / s.sum()


def compare_hourly(bike_profile: pd.DataFrame, taxi_profile: pd.DataFrame,
                   day_type: str = "weekday") -> tuple[pd.DataFrame, float]:
    """Hourly shares for bikes vs taxis and their Pearson correlation."""
    bike = normalised_hourly(bike_profile, "avg_trips", day_type)
    taxi = normalised_hourly(taxi_profile, "avg_pickups", day_type)
    out = pd.DataFrame({"hour": range(24), "bike_share": bike.values.round(4),
                        "taxi_share": taxi.values.round(4)})
    return out, float(np.corrcoef(bike.values, taxi.values)[0, 1])
