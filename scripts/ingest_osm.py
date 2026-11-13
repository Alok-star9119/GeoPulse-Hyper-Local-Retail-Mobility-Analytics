"""Run the Day 4 OpenStreetMap retail-POI ingestion (needs internet).

Usage:  python scripts/ingest_osm.py [--radius 500] [--refresh]

Outputs
  data/raw/osm/osm_pois_raw.json            raw Overpass response     (git-ignored)
  data/interim/osm_pois.csv                 cleaned POIs + nearest hub (git-ignored)
  reports/tables/osm_category_counts.csv    POIs and data quality by category (committed)
  reports/tables/osm_hub_summary.csv        POIs around each hub              (committed)
  reports/figures/osm_hub_poi_mix.png       stacked bar chart                 (committed)
Data (c) OpenStreetMap contributors, ODbL.
"""
import argparse

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from geopulse.config import FIGURES_DIR, INTERIM_DIR, REPORTS_DIR, ensure_directories
from geopulse.ingest_osm import (assign_nearest_hub, category_counts, clean_pois,
                                 fetch_cached, hub_summary, parse_elements)
from geopulse.sources import get_hubs, load_study_area, mark_verified

NON_CAT_COLS = {"hub_id", "hub_name", "hub_type", "radius_m", "poi_total", "poi_per_km2", "named_share"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--radius", type=float, default=500, help="hub catchment radius in metres")
    ap.add_argument("--refresh", action="store_true", help="ignore cached download")
    args = ap.parse_args()

    ensure_directories()
    tables = REPORTS_DIR / "tables"
    tables.mkdir(parents=True, exist_ok=True)

    area = load_study_area()
    hubs = get_hubs(area)

    raw = fetch_cached(area["bbox"], refresh=args.refresh)
    mark_verified("osm_pois")

    pois = clean_pois(parse_elements(raw), area["bbox"])
    pois = assign_nearest_hub(pois, hubs)
    pois.to_csv(INTERIM_DIR / "osm_pois.csv", index=False)

    cats = category_counts(pois)
    cats.to_csv(tables / "osm_category_counts.csv", index=False)
    summary = hub_summary(pois, hubs, args.radius)
    summary.to_csv(tables / "osm_hub_summary.csv", index=False)
    print(f"{len(pois)} POIs\n", cats.to_string(index=False), "\n")
    print(summary[["hub_name", "poi_total", "poi_per_km2"]].to_string(index=False))

    cat_cols = [c for c in summary.columns if c not in NON_CAT_COLS]
    by_hub = summary.set_index("hub_name")
    plot_df = by_hub.loc[by_hub["poi_total"].sort_values().index, cat_cols]
    ax = plot_df.plot(kind="barh", stacked=True, figsize=(9, 5.5), colormap="tab10")
    ax.set_title(f"Retail POIs within {args.radius:.0f} m of each hub (OpenStreetMap)")
    ax.set_xlabel("Number of POIs")
    ax.set_ylabel("")
    ax.legend(fontsize=8, loc="lower right")
    ax.figure.savefig(FIGURES_DIR / "osm_hub_poi_mix.png", dpi=150, bbox_inches="tight")
    print("Done. Commit reports/ and data/reference/.")


if __name__ == "__main__":
    main()
