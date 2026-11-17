"""Day 8: assign Manhattan taxi zones to the 10 retail hubs.

Usage
  python scripts/map_zones_to_hubs.py                    # downloads TLC taxi-zone shapes
  python scripts/map_zones_to_hubs.py --shapes my.zip    # or use a file you downloaded
  python scripts/map_zones_to_hubs.py --radius 700       # change the catchment radius

Outputs
  data/raw/tlc/taxi_zones.zip                   shapes download          (git-ignored)
  data/reference/zone_hub_map.csv               zone -> hub table        (committed)
  reports/tables/zone_hub_coverage.csv          zones per hub            (committed)
  reports/figures/zones_hub_map.png             map of zones by hub      (committed)
Then re-run scripts/build_panel.py so the hub panel gets taxi pickups.
Rule: each zone goes to the hub with the nearest boundary (ties: nearest centroid), kept only
if within the radius. See src/geopulse/zones.py.
"""
import argparse

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from geopulse.config import FIGURES_DIR, REFERENCE_DIR, REPORTS_DIR, ensure_directories
from geopulse.sources import ensure_source, get_hubs, mark_verified
from geopulse.zones import (download_zone_shapes, load_zone_shapes, mapping_report,
                            zone_hub_table)

CATALOG_ROW = {
    "source_id": "tlc_zone_shapes", "name": "NYC TLC Taxi Zone Shapes", "category": "reference",
    "role": "Zone polygons used to map taxi pickups to retail hubs", "priority": "secondary",
    "granularity": "zone", "file_format": "shapefile_zip", "access_method": "direct_download",
    "landing_page": "https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page",
    "url_template": "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zones.zip",
    "coverage": "NYC", "licence": "NYC Open Data terms", "attribution_required": "yes",
    "status": "unverified", "last_verified": "",
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--radius", type=float, default=500, help="max boundary distance hub -> zone (m)")
    ap.add_argument("--shapes", help="local .zip / .shp / .geojson of taxi zones (skips download)")
    args = ap.parse_args()

    ensure_directories()
    tables = REPORTS_DIR / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    hubs = get_hubs()
    ensure_source(CATALOG_ROW)

    if args.shapes:
        path = args.shapes
    else:
        path = download_zone_shapes()
        mark_verified("tlc_zone_shapes")

    gdf = load_zone_shapes(path)
    print(f"{len(gdf)} Manhattan taxi zones loaded")

    zmap = zone_hub_table(gdf, hubs, args.radius)
    zmap.to_csv(REFERENCE_DIR / "zone_hub_map.csv", index=False)
    report = mapping_report(zmap, hubs)
    report.to_csv(tables / "zone_hub_coverage.csv", index=False)
    print(report.to_string(index=False))
    empty = report[report["zones_assigned"] == 0]["hub_name"].tolist()
    if empty:
        print(f"\nWARNING: no zone assigned to {empty}. Try a larger --radius or check hub coordinates.")
    print(f"\n{zmap['hub_id'].notna().sum()} of {len(zmap)} zones assigned to a hub")

    # map: assigned zones coloured by hub, others grey
    g = gdf.merge(zmap[["LocationID", "hub_id"]], on="LocationID")
    fig, ax = plt.subplots(figsize=(6, 10))
    g[g["hub_id"].isna()].plot(ax=ax, color="#eeeeee", edgecolor="#bbbbbb", linewidth=0.5)
    assigned = g[g["hub_id"].notna()]
    if len(assigned):
        assigned.plot(ax=ax, column="hub_id", categorical=True, cmap="tab10",
                      edgecolor="white", linewidth=0.6)
    for h in hubs:
        ax.scatter(h.lon, h.lat, s=25, color="black", zorder=3)
        ax.annotate(h.hub_id, (h.lon, h.lat), xytext=(4, 3), textcoords="offset points", fontsize=8)
    ax.set_title(f"Taxi zones assigned to retail hubs (<= {args.radius:.0f} m)")
    ax.set_axis_off()
    fig.savefig(FIGURES_DIR / "zones_hub_map.png", dpi=150, bbox_inches="tight")
    print("Done. Commit data/reference/zone_hub_map.csv, reports/ and the catalog.")


if __name__ == "__main__":
    main()
