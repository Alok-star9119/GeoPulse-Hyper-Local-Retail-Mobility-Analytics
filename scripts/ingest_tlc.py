"""Run the Day 3 TLC ingestion for one month (needs internet and pyarrow).

Usage:  python scripts/ingest_tlc.py --year 2024 --month 1

Outputs
  data/raw/tlc/...                     downloaded files        (git-ignored)
  data/interim/tlc_manhattan_YYYY-MM.parquet  cleaned trips    (git-ignored)
  reports/tables/tlc_quality_YYYY-MM.json     quality report   (committed)
  reports/tables/tlc_hourly_profile_YYYY-MM.csv  hourly demand (committed)
  reports/figures/tlc_hourly_profile_YYYY-MM.png chart         (committed)
"""
import argparse
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from geopulse.config import FIGURES_DIR, INTERIM_DIR, REPORTS_DIR, ensure_directories
from geopulse.ingest_tlc import (basic_clean, download_trips, download_zone_lookup,
                                 filter_manhattan_pickups, hourly_profile,
                                 load_trips, load_zones, validate_trips)
from geopulse.sources import mark_verified


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2024)
    ap.add_argument("--month", type=int, default=1)
    args = ap.parse_args()
    ym = f"{args.year}-{args.month:02d}"

    ensure_directories()
    tables = REPORTS_DIR / "tables"
    tables.mkdir(parents=True, exist_ok=True)

    trips_path = download_trips(args.year, args.month)
    zones_path = download_zone_lookup()
    mark_verified("tlc_trips")
    mark_verified("tlc_zone_lookup")

    trips = load_trips(trips_path)
    zones = load_zones(zones_path)

    report = validate_trips(trips, args.year, args.month)
    clean = basic_clean(trips, args.year, args.month)
    manhattan = filter_manhattan_pickups(clean, zones)
    report.update(rows_after_clean=len(clean), rows_manhattan_pickups=len(manhattan))
    (tables / f"tlc_quality_{ym}.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))

    manhattan.to_parquet(INTERIM_DIR / f"tlc_manhattan_{ym}.parquet", index=False)

    prof = hourly_profile(manhattan, zones)
    prof.to_csv(tables / f"tlc_hourly_profile_{ym}.csv", index=False)

    # Chart: citywide (Manhattan) average pickups per hour, weekday vs weekend
    city = prof.groupby(["day_type", "hour"])["avg_pickups"].sum().unstack(0)
    ax = city.plot(figsize=(8, 4.5), marker="o")
    ax.set_title(f"Manhattan taxi pickups by hour of day ({ym})")
    ax.set_xlabel("Hour of day")
    ax.set_ylabel("Average pickups per day")
    ax.set_xticks(range(0, 24, 2))
    ax.grid(alpha=0.3)
    ax.figure.savefig(FIGURES_DIR / f"tlc_hourly_profile_{ym}.png", dpi=150, bbox_inches="tight")
    print("Done. Commit the files in reports/ and data/reference/.")


if __name__ == "__main__":
    main()
