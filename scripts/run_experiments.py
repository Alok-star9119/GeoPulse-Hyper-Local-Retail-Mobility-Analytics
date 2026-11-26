"""Day 17: run the two experiments (hub clustering vs rule labels; rain by daypart + forecast ablation).

Usage
  python scripts/run_experiments.py --year 2024 --month 1

Needs the Day 5 panel and Day 9 rhythm tables for that month. Outputs (committed):
  reports/tables/experiment_hub_clusters_YYYY-MM.csv, experiment_cluster_summary_YYYY-MM.csv,
  experiment_rain_daypart_YYYY-MM.csv, experiment_forecast_ablation_YYYY-MM.csv
  reports/day17_experiments_YYYY-MM.md
"""
import argparse

import pandas as pd

from geopulse import experiments as ex
from geopulse.config import REPORTS_DIR, ensure_directories


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2024)
    ap.add_argument("--month", type=int, default=1)
    ap.add_argument("--test-days", type=int, default=7)
    a = ap.parse_args()
    ym = f"{a.year}-{a.month:02d}"
    ensure_directories()
    t = REPORTS_DIR / "tables"
    need = [f"city_hourly_panel_{ym}.csv", f"hub_rhythm_stats_{ym}.csv", f"hub_hourly_rhythm_{ym}.csv"]
    for f in need:
        if not (t / f).exists():
            raise SystemExit(f"{f} not found. Run build_panel.py and eda_hub_rhythm.py for {ym} first.")
    city = pd.read_csv(t / need[0], parse_dates=["datetime"])
    stats, rhythm = pd.read_csv(t / need[1]), pd.read_csv(t / need[2])

    clusters, summaries = [], []
    for metric in rhythm["metric"].unique():
        c, s = ex.cluster_hubs(rhythm, stats, metric)
        clusters.append(c)
        summaries.append(s)
    clusters = pd.concat([c for c in clusters if len(c)], ignore_index=True) if any(len(c) for c in clusters) else pd.DataFrame()
    targets = [m for m in ("taxi_pickups", "bike_starts_hubs") if m in city.columns]
    rain = ex.rain_by_daypart(city, targets)
    ablation = pd.concat([ex.forecast_ablation(city, m, a.test_days) for m in targets], ignore_index=True)

    clusters.to_csv(t / f"experiment_hub_clusters_{ym}.csv", index=False)
    pd.DataFrame(summaries).to_csv(t / f"experiment_cluster_summary_{ym}.csv", index=False)
    rain.to_csv(t / f"experiment_rain_daypart_{ym}.csv", index=False)
    ablation.to_csv(t / f"experiment_forecast_ablation_{ym}.csv", index=False)
    out = REPORTS_DIR / f"day17_experiments_{ym}.md"
    out.write_text(ex.render_report(ym, summaries, clusters, rain, ablation), encoding="utf-8")
    print(ablation.to_string(index=False))
    print(f"\nReport: {out}")


if __name__ == "__main__":
    main()
