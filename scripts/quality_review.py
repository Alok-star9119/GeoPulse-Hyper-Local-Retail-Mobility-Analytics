"""Day 7: run the Week 1 data-quality review on the combined hourly tables.

Run after scripts/build_panel.py, for the same month:
  python scripts/quality_review.py --year 2024 --month 1

Outputs
  reports/tables/quality_checks_YYYY-MM.csv     one row per check            (committed)
  reports/tables/quality_anomalies_YYYY-MM.csv  unusual hours (flagged only) (committed)
  reports/week1_data_quality_report_YYYY-MM.md  readable report              (committed)
  reports/figures/quality_anomalies_YYYY-MM.png chart with flagged hours     (committed)
Exit code is 1 if any check FAILS, so it can be used as a gate.
"""
import argparse
import json
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from geopulse.config import FIGURES_DIR, REPORTS_DIR, ensure_directories
from geopulse.quality import render_report, run_all
from geopulse.sources import get_hubs, load_catalog


def read_json(path):
    return json.loads(path.read_text()) if path.exists() else None


def lineage_table(tables, ym) -> pd.DataFrame:
    rows = []
    for f in sorted(tables.glob(f"*{ym}*")):
        if f.name.startswith("quality_"):
            continue
        n = (sum(1 for _ in open(f, encoding="utf-8")) - 1) if f.suffix == ".csv" else "-"
        rows.append({"file": f"reports/tables/{f.name}", "rows": n})
    return pd.DataFrame(rows, columns=["file", "rows"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2024)
    ap.add_argument("--month", type=int, default=1)
    args = ap.parse_args()
    y, m = args.year, args.month
    ym = f"{y}-{m:02d}"

    ensure_directories()
    tables = REPORTS_DIR / "tables"
    city_path, hub_path = tables / f"city_hourly_panel_{ym}.csv", tables / f"hub_hourly_panel_{ym}.csv"
    for f in (city_path, hub_path):
        if not f.exists():
            raise SystemExit(f"{f.name} not found. Run scripts/build_panel.py --year {y} --month {m} first.")

    city = pd.read_csv(city_path, parse_dates=["datetime"])
    hub = pd.read_csv(hub_path, parse_dates=["datetime"])
    results, anomalies = run_all(
        city, hub, y, m, hubs_count=len(get_hubs()), catalog=load_catalog(),
        tlc_report=read_json(tables / f"tlc_quality_{ym}.json"),
        bike_report=read_json(tables / f"citibike_quality_{ym}.json"))

    results.to_csv(tables / f"quality_checks_{ym}.csv", index=False)
    anomalies.to_csv(tables / f"quality_anomalies_{ym}.csv", index=False)
    report = render_report(results, anomalies, lineage_table(tables, ym), ym)
    (REPORTS_DIR / f"week1_data_quality_report_{ym}.md").write_text(report, encoding="utf-8")
    print(results[["status", "check", "scope", "detail"]].to_string(index=False))

    # chart: hourly series with flagged hours marked
    fig, axs = plt.subplots(2, 1, figsize=(11, 6), sharex=True)
    for ax, col, lab in ((axs[0], "taxi_pickups", "Taxi pickups"), (axs[1], "bike_starts_hubs", "Bike starts (hubs)")):
        ax.plot(city["datetime"], city[col], lw=0.8, color="#1b4f72")
        a = anomalies[anomalies["metric"] == col] if len(anomalies) else anomalies
        if len(a):
            ax.scatter(a["datetime"], a["value"], color="#d95f02", s=22, zorder=3, label="unusual hour")
            ax.legend(fontsize=8, loc="upper right")
        ax.set_ylabel(lab)
    axs[0].set_title(f"Hourly trips with unusual hours flagged, {ym}")
    fig.autofmt_xdate()
    fig.savefig(FIGURES_DIR / f"quality_anomalies_{ym}.png", dpi=150, bbox_inches="tight")

    fails = int((results["status"] == "fail").sum())
    print(f"\nReport: reports/week1_data_quality_report_{ym}.md  ({fails} FAIL)")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
