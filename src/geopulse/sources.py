"""Load and validate the GeoPulse data-source catalog and study area."""
from __future__ import annotations

import json
from dataclasses import dataclass

import pandas as pd

from geopulse.config import REFERENCE_DIR

CATALOG_PATH = REFERENCE_DIR / "data_sources_catalog.csv"
STUDY_AREA_PATH = REFERENCE_DIR / "study_area.json"

REQUIRED_COLUMNS = [
    "source_id", "name", "category", "role", "priority", "granularity",
    "file_format", "access_method", "landing_page", "url_template",
    "coverage", "licence", "attribution_required", "status", "last_verified",
]
VALID_PRIORITIES = {"primary", "primary_fallback", "secondary", "context", "optional"}
VALID_STATUS = {"unverified", "verified", "planned", "unavailable"}


@dataclass(frozen=True)
class Hub:
    hub_id: str
    name: str
    type: str
    lat: float
    lon: float


def load_catalog(path=CATALOG_PATH) -> pd.DataFrame:
    """Read the catalog CSV and validate it. Raises ValueError if invalid."""
    df = pd.read_csv(path, dtype=str).fillna("")
    validate_catalog(df)
    return df


def validate_catalog(df: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Catalog is missing columns: {missing}")
    if df["source_id"].duplicated().any():
        raise ValueError("Catalog has duplicate source_id values")
    if (df["source_id"].str.strip() == "").any():
        raise ValueError("Catalog has an empty source_id")
    bad_priority = set(df["priority"]) - VALID_PRIORITIES
    if bad_priority:
        raise ValueError(f"Invalid priority values: {sorted(bad_priority)}")
    bad_status = set(df["status"]) - VALID_STATUS
    if bad_status:
        raise ValueError(f"Invalid status values: {sorted(bad_status)}")


def mark_verified(source_id: str, path=CATALOG_PATH, on: str | None = None) -> None:
    """Set status=verified and last_verified=<today> for a source in the catalog."""
    from datetime import date
    df = load_catalog(path)
    if source_id not in set(df["source_id"]):
        raise KeyError(source_id)
    mask = df["source_id"] == source_id
    df.loc[mask, "status"] = "verified"
    df.loc[mask, "last_verified"] = on or date.today().isoformat()
    df.to_csv(path, index=False)


def load_study_area(path=STUDY_AREA_PATH) -> dict:
    """Read the study-area JSON and validate the bounding box and hubs."""
    with open(path, encoding="utf-8") as f:
        area = json.load(f)
    bbox = area["bbox"]
    if not (bbox["min_lat"] < bbox["max_lat"] and bbox["min_lon"] < bbox["max_lon"]):
        raise ValueError("Invalid bounding box")
    for hub in area["hubs"]:
        if not in_bbox(hub["lat"], hub["lon"], bbox):
            raise ValueError(f"Hub {hub['hub_id']} lies outside the bounding box")
    ids = [h["hub_id"] for h in area["hubs"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate hub_id in study area")
    return area


def in_bbox(lat: float, lon: float, bbox: dict) -> bool:
    return (bbox["min_lat"] <= lat <= bbox["max_lat"]
            and bbox["min_lon"] <= lon <= bbox["max_lon"])


def get_hubs(area: dict | None = None) -> list[Hub]:
    area = area or load_study_area()
    return [Hub(**h) for h in area["hubs"]]


def tlc_trip_url(year: int, month: int, kind: str = "yellow") -> str:
    """Build the TLC monthly trip file URL. Verify the pattern before bulk download."""
    if not 1 <= month <= 12:
        raise ValueError("month must be 1-12")
    return (f"https://d37ci6vzurychx.cloudfront.net/trip-data/"
            f"{kind}_tripdata_{year}-{month:02d}.parquet")
