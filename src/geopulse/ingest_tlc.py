"""Day 3: ingest NYC TLC yellow-taxi trips and the taxi-zone lookup.

Pipeline: download -> load needed columns -> validate -> keep Manhattan -> hourly profile.
All transformation functions work on DataFrames so they can be tested without files.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from geopulse.config import RAW_DIR
from geopulse.download import download_file
from geopulse.logger import get_logger
from geopulse.sources import tlc_trip_url

log = get_logger(__name__)

ZONE_LOOKUP_URL = "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv"
TLC_RAW_DIR = RAW_DIR / "tlc"

# Only these columns are read from the (large) parquet file.
TRIP_COLUMNS = [
    "tpep_pickup_datetime", "tpep_dropoff_datetime",
    "PULocationID", "DOLocationID",
    "passenger_count", "trip_distance", "total_amount",
]
ZONE_COLUMNS = ["LocationID", "Borough", "Zone", "service_zone"]

MAX_TRIP_HOURS = 6          # longer trips are treated as errors
MAX_TRIP_MILES = 100        # longer distances are treated as errors


# ---------- download / load ----------
def download_trips(year: int, month: int, kind: str = "yellow") -> Path:
    url = tlc_trip_url(year, month, kind)
    return download_file(url, TLC_RAW_DIR / f"{kind}_tripdata_{year}-{month:02d}.parquet")


def download_zone_lookup() -> Path:
    return download_file(ZONE_LOOKUP_URL, TLC_RAW_DIR / "taxi_zone_lookup.csv")


def load_trips(path: Path, columns: list[str] = TRIP_COLUMNS) -> pd.DataFrame:
    """Read selected columns from a TLC parquet file (needs pyarrow)."""
    return pd.read_parquet(path, columns=columns)


def load_zones(path: Path) -> pd.DataFrame:
    zones = pd.read_csv(path)
    missing = [c for c in ZONE_COLUMNS if c not in zones.columns]
    if missing:
        raise ValueError(f"Zone lookup is missing columns: {missing}")
    return zones


# ---------- validation ----------
def validate_trips(df: pd.DataFrame, year: int, month: int) -> dict:
    """Return a data-quality report (dict). Does not modify the data."""
    pickup, dropoff = df["tpep_pickup_datetime"], df["tpep_dropoff_datetime"]
    duration_h = (dropoff - pickup).dt.total_seconds() / 3600
    in_month = (pickup.dt.year == year) & (pickup.dt.month == month)
    return {
        "rows": int(len(df)),
        "year": year,
        "month": month,
        "pickup_min": str(pickup.min()),
        "pickup_max": str(pickup.max()),
        "null_counts": {c: int(v) for c, v in df.isna().sum().items() if v > 0},
        "pickup_outside_month": int((~in_month).sum()),
        "dropoff_before_pickup": int((duration_h < 0).sum()),
        "duration_over_limit": int((duration_h > MAX_TRIP_HOURS).sum()),
        "non_positive_distance": int((df["trip_distance"] <= 0).sum()),
        "distance_over_limit": int((df["trip_distance"] > MAX_TRIP_MILES).sum()),
        "negative_amount": int((df["total_amount"] < 0).sum()),
        "duplicate_rows": int(df.duplicated().sum()),
    }


# ---------- cleaning / filtering ----------
def basic_clean(df: pd.DataFrame, year: int, month: int) -> pd.DataFrame:
    """Drop rows that are clearly invalid. Keeps only the target month."""
    duration_h = (df["tpep_dropoff_datetime"] - df["tpep_pickup_datetime"]).dt.total_seconds() / 3600
    keep = (
        (df["tpep_pickup_datetime"].dt.year == year)
        & (df["tpep_pickup_datetime"].dt.month == month)
        & (duration_h > 0) & (duration_h <= MAX_TRIP_HOURS)
        & (df["trip_distance"] > 0) & (df["trip_distance"] <= MAX_TRIP_MILES)
        & (df["total_amount"] >= 0)
        & df["PULocationID"].notna()
    )
    out = df.loc[keep].drop_duplicates().reset_index(drop=True)
    log.info("basic_clean kept %d of %d rows", len(out), len(df))
    return out


def manhattan_zone_ids(zones: pd.DataFrame) -> set[int]:
    return set(zones.loc[zones["Borough"] == "Manhattan", "LocationID"].astype(int))


def filter_manhattan_pickups(trips: pd.DataFrame, zones: pd.DataFrame) -> pd.DataFrame:
    ids = manhattan_zone_ids(zones)
    return trips[trips["PULocationID"].isin(ids)].reset_index(drop=True)


# ---------- aggregation ----------
def hourly_profile(trips: pd.DataFrame, zones: pd.DataFrame) -> pd.DataFrame:
    """Average pickups per hour-of-day, by zone and day type (weekday/weekend).

    Output columns: PULocationID, Zone, day_type, hour, pickups_total, days, avg_pickups
    """
    t = trips.copy()
    t["date"] = t["tpep_pickup_datetime"].dt.date
    t["hour"] = t["tpep_pickup_datetime"].dt.hour
    t["day_type"] = (t["tpep_pickup_datetime"].dt.dayofweek >= 5).map(
        {True: "weekend", False: "weekday"})

    # Divide by calendar days in the month (not days that happen to have data),
    # so quiet zones are not inflated.
    first = t["tpep_pickup_datetime"].min()
    month_days = pd.date_range(first.replace(day=1).normalize(), periods=first.days_in_month)
    days = (pd.Series(month_days.dayofweek >= 5)
            .map({True: "weekend", False: "weekday"})
            .value_counts().rename_axis("day_type").rename("days").reset_index())
    prof = (t.groupby(["PULocationID", "day_type", "hour"]).size()
            .rename("pickups_total").reset_index())
    prof = prof.merge(days, on="day_type")
    prof["avg_pickups"] = (prof["pickups_total"] / prof["days"]).round(2)
    prof = prof.merge(zones[["LocationID", "Zone"]],
                      left_on="PULocationID", right_on="LocationID", how="left").drop(columns="LocationID")
    return prof[["PULocationID", "Zone", "day_type", "hour",
                 "pickups_total", "days", "avg_pickups"]]
