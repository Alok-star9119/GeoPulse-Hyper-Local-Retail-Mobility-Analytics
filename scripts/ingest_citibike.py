"""Run the Day 5 Citi Bike ingestion for one month (needs internet unless --file is given).

Usage
  python scripts/ingest_citibike.py --year 2024 --month 1
  python scripts/ingest_citibike.py --year 2024 --month 1 --url <direct zip link>
  python scripts/ingest_citibike.py --year 2024 --month 1 --file path/to/downloaded.zip

Outputs
  data/raw/citibike/...                                 downloaded file   (git-ignored)
  reports/tables/citibike_quality_YYYY-MM.json          row counts        (committed)
  reports/tables/citibike_station_summary_YYYY-MM.csv   one row/station   (committed)
  reports/tables/citibike_hub_summary_YYYY-MM.csv       one row/hub       (committed)
  reports/tables/citibike_hub_hourly_YYYY-MM.csv        hub x hour        (committed)
  reports/tables/bike_vs_taxi_hourly_YYYY-MM.csv        only if Day 3 table exists
  reports/figures/citibike_vs_taxi_hourly_YYYY-MM.png   only if Day 3 table exists
  reports/figures/citibike_hub_trips_YYYY-MM.png        trips by hub, member vs casual
"""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from geopulse.config import FIGURES_DIR, REPORTS_DIR, ensure_directories
from geopulse.ingest_citibike import (assign_hubs, compare_hourly, download_month,
                                      hub_hourly_profile, hub_summary, process_file,
                                      station_table)
from geopulse.sources import get_hubs, load_study_area, mark_verified


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2024)
    ap.add_argument("--month", type=int, default=1)
    ap.add_argument("--radius", type=float, default=500, help="hub radius in metres")
    ap.add_argument("--url", help="direct link to the monthly zip")
    ap.add_argument("--file", help="already-downloaded zip/csv")
    args = ap.parse_args()
    ym = f"{args.year}-{args.month:02d}"

    ensure_directories()
    tables = REPORTS_DIR / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    area = load_study_area()
    hubs = get_hubs(area)

    path = Path(args.file) if args.file else download_month(args.year, args.month, args.url)
    mark_verified("citibike_trips")

    agg, report = process_file(path, area["bbox"], args.year, args.month)
    (tables / f"citibike_quality_{ym}.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))

    stations = assign_hubs(station_table(agg), hubs, args.radius)
    stations.sort_values("trips", ascending=False).to_csv(
        tables / f"citibike_station_summary_{ym}.csv", index=False)

    profile = hub_hourly_profile(agg, stations, args.year, args.month)
    profile.to_csv(tables / f"citibike_hub_hourly_{ym}.csv", index=False)
    summary = hub_summary(stations, profile, hubs, args.radius)
    summary.to_csv(tables / f"citibike_hub_summary_{ym}.csv", index=False)
    print(summary.to_string(index=False))

    # Chart 1: trips near each hub, member vs casual
    mapping = stations.loc[stations.hub_id.notna(), ["station_id", "hub_id"]]
    a = agg.merge(mapping, left_on="start_station_id", right_on="station_id")
    names = {h.hub_id: h.name for h in hubs}
    pivot = (a.groupby(["hub_id", "user_type"])["trips"].sum().unstack(fill_value=0)
             .rename(index=names))
    pivot = pivot.loc[pivot.sum(axis=1).sort_values().index]
    ax = pivot.plot(kind="barh", stacked=True, figsize=(9, 5.5), color=["#d95f02", "#1b4f72", "#999999"][:pivot.shape[1]])
    ax.set_title(f"Citi Bike trip starts within {args.radius:.0f} m of each hub ({ym})")
    ax.set_xlabel("Trips")
    ax.set_ylabel("")
    ax.figure.savefig(FIGURES_DIR / f"citibike_hub_trips_{ym}.png", dpi=150, bbox_inches="tight")
    plt.close(ax.figure)

    # Comparison with Day 3 taxi profile (if that table is present)
    taxi_path = tables / f"tlc_hourly_profile_{ym}.csv"
    if taxi_path.exists():
        cmp_df, corr = compare_hourly(profile, pd.read_csv(taxi_path))
        cmp_df.to_csv(tables / f"bike_vs_taxi_hourly_{ym}.csv", index=False)
        ax = cmp_df.set_index("hour")[["bike_share", "taxi_share"]].plot(figsize=(8, 4.5), marker="o")
        ax.set_title(f"Weekday hourly pattern: bikes vs taxis ({ym}), correlation {corr:.2f}")
        ax.set_ylabel("Share of the day's trips")
        ax.set_xticks(range(0, 24, 2))
        ax.grid(alpha=0.3)
        ax.figure.savefig(FIGURES_DIR / f"citibike_vs_taxi_hourly_{ym}.png", dpi=150, bbox_inches="tight")
        print(f"Weekday hourly correlation bikes vs taxis: {corr:.2f}")
    else:
        print(f"Note: {taxi_path.name} not found, run scripts/ingest_tlc.py first for the taxi comparison.")
    print("Done. Commit reports/ and data/reference/.")


if __name__ == "__main__":
    main()
