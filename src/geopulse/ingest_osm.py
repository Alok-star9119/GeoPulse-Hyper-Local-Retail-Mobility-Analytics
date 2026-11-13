"""Day 4: ingest retail POIs (shops, food, services) from OpenStreetMap via Overpass.

Data (c) OpenStreetMap contributors, licensed under ODbL (https://www.openstreetmap.org/copyright).

Pipeline: build query -> fetch JSON -> parse to DataFrame -> clean -> categorise
-> summarise POIs around each retail hub.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

from geopulse.config import RAW_DIR
from geopulse.geo import haversine_m_array
from geopulse.logger import get_logger

log = get_logger(__name__)

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
OSM_RAW_DIR = RAW_DIR / "osm"

AMENITIES = ["restaurant", "cafe", "fast_food", "bar", "pub", "bank", "pharmacy", "marketplace"]

# OSM tag value -> GeoPulse retail category
SHOP_CATEGORY = {
    **dict.fromkeys(["supermarket", "convenience", "greengrocer", "bakery", "butcher", "deli",
                     "alcohol", "beverages", "confectionery", "seafood", "health_food",
                     "pastry", "coffee", "cheese"], "food_retail"),
    **dict.fromkeys(["clothes", "shoes", "boutique", "jewelry", "bag", "fashion_accessories",
                     "tailor", "watches", "fashion"], "fashion"),
    **dict.fromkeys(["hairdresser", "beauty", "cosmetics", "chemist", "optician", "massage",
                     "perfumery", "pharmacy", "tattoo", "nail_salon"], "beauty_health"),
    **dict.fromkeys(["electronics", "mobile_phone", "computer", "furniture", "hardware",
                     "doityourself", "interior_decoration", "houseware", "appliance",
                     "bed", "lighting"], "electronics_home"),
    **dict.fromkeys(["department_store", "mall", "gift", "books", "toys", "sports", "music",
                     "art", "florist", "variety_store", "stationery", "second_hand",
                     "musical_instrument", "video_games"], "general_gifts"),
}
AMENITY_CATEGORY = {
    **dict.fromkeys(["restaurant", "cafe", "fast_food", "bar", "pub"], "food_beverage"),
    "bank": "services",
    "pharmacy": "beauty_health",
    "marketplace": "general_gifts",
}


# ---------- query / fetch ----------
def build_query(bbox: dict, timeout: int = 180) -> str:
    """Overpass QL for shops and selected amenities inside a bbox (S, W, N, E order)."""
    s, w, n, e = bbox["min_lat"], bbox["min_lon"], bbox["max_lat"], bbox["max_lon"]
    box = f"({s},{w},{n},{e})"
    amen = "|".join(AMENITIES)
    return (f"[out:json][timeout:{timeout}];\n"
            f"(\n  nwr[\"shop\"]{box};\n  nwr[\"amenity\"~\"^({amen})$\"]{box};\n);\n"
            f"out center tags;")


def fetch_overpass(query: str, urls: list[str] | None = None, retries: int = 2,
                   timeout: int = 240) -> dict:
    """POST the query to each endpoint in turn until one succeeds."""
    last: Exception | None = None
    for url in urls or OVERPASS_URLS:
        for attempt in range(1, retries + 1):
            try:
                body = urllib.parse.urlencode({"data": query}).encode()
                req = urllib.request.Request(
                    url, data=body, headers={"User-Agent": "geopulse-intern-project"})
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                if "elements" not in data:
                    raise ValueError("Response has no 'elements'")
                log.info("Overpass OK (%s): %d elements", url, len(data["elements"]))
                return data
            except Exception as err:
                last = err
                log.warning("Overpass %s attempt %d/%d failed: %s", url, attempt, retries, err)
                time.sleep(min(5 * attempt, 20))
    raise RuntimeError("All Overpass endpoints failed") from last


def fetch_cached(bbox: dict, path: Path | None = None, refresh: bool = False) -> dict:
    """Fetch POIs, caching the raw JSON so reruns do not hit the public API."""
    path = path or OSM_RAW_DIR / "osm_pois_raw.json"
    if path.exists() and not refresh:
        log.info("Using cached %s", path)
        return json.loads(path.read_text(encoding="utf-8"))
    data = fetch_overpass(build_query(bbox))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return data


# ---------- parse / clean ----------
def parse_elements(data: dict) -> pd.DataFrame:
    """Turn Overpass JSON into one row per POI."""
    rows = []
    for el in data.get("elements", []):
        tags = el.get("tags", {}) or {}
        lat = el.get("lat", (el.get("center") or {}).get("lat"))
        lon = el.get("lon", (el.get("center") or {}).get("lon"))
        rows.append({
            "osm_type": el.get("type"),
            "osm_id": el.get("id"),
            "lat": lat,
            "lon": lon,
            "name": tags.get("name"),
            "shop": tags.get("shop"),
            "amenity": tags.get("amenity"),
            "brand": tags.get("brand"),
            "has_opening_hours": "opening_hours" in tags,
        })
    return pd.DataFrame(rows, columns=[
        "osm_type", "osm_id", "lat", "lon", "name", "shop", "amenity", "brand", "has_opening_hours"])


def categorise(shop, amenity) -> str:
    """Map OSM tags to a GeoPulse retail category. Shop tag wins over amenity."""
    if isinstance(shop, str) and shop:
        return SHOP_CATEGORY.get(shop, "other_shop")
    if isinstance(amenity, str) and amenity:
        return AMENITY_CATEGORY.get(amenity, "other_shop")
    return "other_shop"


def clean_pois(df: pd.DataFrame, bbox: dict) -> pd.DataFrame:
    """Drop rows without coordinates, outside the bbox or duplicated; add category."""
    out = df.dropna(subset=["lat", "lon"]).copy()
    out = out[(out.lat.between(bbox["min_lat"], bbox["max_lat"]))
              & (out.lon.between(bbox["min_lon"], bbox["max_lon"]))]
    out = out.drop_duplicates(subset=["osm_type", "osm_id"])
    out["category"] = [categorise(s, a) for s, a in zip(out["shop"], out["amenity"])]
    log.info("clean_pois kept %d of %d rows", len(out), len(df))
    return out.reset_index(drop=True)


# ---------- hub analysis ----------
def assign_nearest_hub(pois: pd.DataFrame, hubs) -> pd.DataFrame:
    """Add nearest_hub_id and nearest_hub_m columns."""
    if pois.empty:
        return pois.assign(nearest_hub_id=pd.Series(dtype=str), nearest_hub_m=pd.Series(dtype=float))
    dists = pd.DataFrame({h.hub_id: haversine_m_array(pois.lat, pois.lon, h.lat, h.lon)
                          for h in hubs})
    out = pois.copy()
    out["nearest_hub_id"] = dists.idxmin(axis=1).values
    out["nearest_hub_m"] = dists.min(axis=1).round(1).values
    return out


def hub_summary(pois: pd.DataFrame, hubs, radius_m: float = 500) -> pd.DataFrame:
    """Count POIs within `radius_m` of each hub, in total and by category."""
    rows = []
    area_km2 = 3.141592653589793 * (radius_m / 1000) ** 2
    for h in hubs:
        d = haversine_m_array(pois.lat, pois.lon, h.lat, h.lon)
        near = pois[d <= radius_m]
        row = {"hub_id": h.hub_id, "hub_name": h.name, "hub_type": h.type,
               "radius_m": radius_m, "poi_total": len(near),
               "poi_per_km2": round(len(near) / area_km2, 1),
               "named_share": round(near["name"].notna().mean(), 3) if len(near) else 0.0}
        counts = near["category"].value_counts()
        for cat in sorted(set(pois["category"])):
            row[cat] = int(counts.get(cat, 0))
        rows.append(row)
    return pd.DataFrame(rows)


def category_counts(pois: pd.DataFrame) -> pd.DataFrame:
    """Overall POI counts and data-quality share by category."""
    g = pois.groupby("category")
    out = pd.DataFrame({
        "poi_count": g.size(),
        "named_share": g["name"].apply(lambda s: round(s.notna().mean(), 3)),
        "opening_hours_share": g["has_opening_hours"].apply(lambda s: round(s.mean(), 3)),
    }).sort_values("poi_count", ascending=False).reset_index()
    return out
