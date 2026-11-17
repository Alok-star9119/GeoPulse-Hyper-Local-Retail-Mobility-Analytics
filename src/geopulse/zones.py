"""Day 8: map NYC taxi zones (polygons) to the 10 retail hubs.

Why: taxi pickups are recorded per taxi zone, not per point. To put taxi demand next to bike
trips and shops in the hub panel, every Manhattan zone is assigned to at most one hub.

Rule (documented, simple, no double counting):
  1. Measure the distance (metres) from each hub centre to each zone's boundary
     (0 if the hub lies inside the zone) and to the zone's centroid.
  2. A zone belongs to the hub with the smallest boundary distance; ties (for example two hubs
     inside one zone) are broken by centroid distance.
  3. The zone is only kept if that distance is <= radius_m (default 500 m); otherwise unassigned.

The geometry functions need geopandas (installed from requirements.txt). The assignment
logic itself is pure pandas.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

import pandas as pd

from geopulse.config import RAW_DIR
from geopulse.download import download_file
from geopulse.logger import get_logger

log = get_logger(__name__)

ZONES_URL = "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zones.zip"
ZONES_DIR = RAW_DIR / "tlc"
UTM_NYC = 32618     # metres; UTM zone 18N covers New York City


# ---------- files ----------
def download_zone_shapes(url: str = ZONES_URL) -> Path:
    return download_file(url, ZONES_DIR / "taxi_zones.zip")


def extract_shapes(zip_path: Path, dest: Path | None = None) -> Path:
    """Unzip a shapefile archive and return the path of the .shp inside."""
    zip_path = Path(zip_path)
    dest = Path(dest) if dest else zip_path.with_suffix("")
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest)
    shp = sorted(dest.rglob("*.shp"))
    if not shp:
        raise ValueError(f"No .shp file found in {zip_path}")
    return shp[0]


# ---------- geometry (needs geopandas) ----------
def load_zone_shapes(path: Path):
    """Read taxi-zone polygons (zip, .shp or .geojson) -> GeoDataFrame in WGS84, Manhattan only."""
    import geopandas as gpd
    path = Path(path)
    if path.suffix.lower() == ".zip":
        path = extract_shapes(path)
    gdf = gpd.read_file(path)
    lower = {c.lower(): c for c in gdf.columns}
    for need in ("locationid", "zone", "borough"):
        if need not in lower:
            raise ValueError(f"Zone file is missing a '{need}' column; found {list(gdf.columns)}")
    gdf = gdf.rename(columns={lower["locationid"]: "LocationID", lower["zone"]: "zone",
                              lower["borough"]: "borough"})
    if gdf.crs is None:
        raise ValueError("Zone file has no coordinate system (CRS)")
    gdf = gdf[gdf["borough"] == "Manhattan"][["LocationID", "zone", "borough", "geometry"]]
    gdf = gdf.dissolve(by="LocationID", as_index=False, aggfunc="first")   # one row per zone ID
    return gdf.to_crs(epsg=4326).reset_index(drop=True)


def zone_hub_distances(gdf, hubs) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (boundary_distance_m, centroid_distance_m): index LocationID, one column per hub."""
    import geopandas as gpd
    z = gdf.to_crs(epsg=UTM_NYC)
    pts = gpd.GeoSeries(gpd.points_from_xy([h.lon for h in hubs], [h.lat for h in hubs]),
                        crs=4326).to_crs(epsg=UTM_NYC)
    centroids = z.geometry.centroid
    boundary = pd.DataFrame({h.hub_id: z.geometry.distance(p) for h, p in zip(hubs, pts)})
    centre = pd.DataFrame({h.hub_id: centroids.distance(p) for h, p in zip(hubs, pts)})
    boundary.index = centre.index = z["LocationID"].astype(int).values
    return boundary.round(1), centre.round(1)


# ---------- assignment (pure pandas) ----------
def assign_zones_to_hubs(boundary: pd.DataFrame, centre: pd.DataFrame,
                         radius_m: float = 500) -> pd.DataFrame:
    """One row per zone: nearest hub, distance, and hub_id (empty if farther than radius_m)."""
    if not boundary.index.equals(centre.index) or list(boundary.columns) != list(centre.columns):
        raise ValueError("boundary and centre tables must have the same zones and hubs")
    rows = []
    for zid in boundary.index:
        order = sorted(boundary.columns,
                       key=lambda h: (round(boundary.at[zid, h]), centre.at[zid, h]))
        best = order[0]
        d = float(boundary.at[zid, best])
        rows.append({"LocationID": int(zid), "nearest_hub_id": best, "hub_distance_m": d,
                     "centroid_distance_m": float(centre.at[zid, best]),
                     "contains_hub": d == 0,
                     "hub_id": best if d <= radius_m else None})
    return pd.DataFrame(rows)


def zone_hub_table(gdf, hubs, radius_m: float = 500) -> pd.DataFrame:
    """Full mapping table with zone names (the file saved to data/reference/zone_hub_map.csv)."""
    boundary, centre = zone_hub_distances(gdf, hubs)
    m = assign_zones_to_hubs(boundary, centre, radius_m)
    names = gdf[["LocationID", "zone"]].astype({"LocationID": int})
    return m.merge(names, on="LocationID", how="left")[
        ["LocationID", "zone", "hub_id", "nearest_hub_id", "hub_distance_m",
         "centroid_distance_m", "contains_hub"]]


def mapping_report(zone_map: pd.DataFrame, hubs) -> pd.DataFrame:
    """Zones per hub, so hubs that received no zone are visible."""
    counts = zone_map["hub_id"].value_counts()
    contains = zone_map[zone_map["contains_hub"]].groupby("hub_id").size()
    return pd.DataFrame([{"hub_id": h.hub_id, "hub_name": h.name,
                          "zones_assigned": int(counts.get(h.hub_id, 0)),
                          "zones_containing_hub": int(contains.get(h.hub_id, 0))} for h in hubs])
