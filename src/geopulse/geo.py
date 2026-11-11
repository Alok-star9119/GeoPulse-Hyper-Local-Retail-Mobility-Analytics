"""Small geographic helpers (no external geo dependencies)."""
from __future__ import annotations

import math

EARTH_RADIUS_M = 6_371_000.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres between two lat/lon points."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def nearest_hub(lat: float, lon: float, hubs) -> tuple[str, float]:
    """Return (hub_id, distance_m) of the closest hub to a point."""
    if not hubs:
        raise ValueError("hubs is empty")
    best = min(hubs, key=lambda h: haversine_m(lat, lon, h.lat, h.lon))
    return best.hub_id, haversine_m(lat, lon, best.lat, best.lon)
