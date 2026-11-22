"""Day 13: baseline hourly demand forecasts (seasonal naive, hour-of-week mean, hour-of-week + weather).

Run after scripts/build_panel.py:
  python scripts/forecast_baseline.py --year 2024 --month 1 --test-days 7

Outputs (committed)
  reports/tables/forecast_metrics_YYYY-MM.csv      city level, one row per target x model
  reports/tables/forecast_hub_metrics_YYYY-MM.csv  hub level WAPE of each model
  reports/figures/forecast_city_YYYY-MM.png        actual vs predicted, test period
  reports/day13_forecast_baselines_YYYY-MM.md      readable report
"""
import argparse

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from geopulse import forecast as fc
from geopulse.config import FIGURES_DIR, REPORTS_DIR, ensure_directories

CITY_TARGETS = ["taxi_pickups", "bike_starts_hubs"]
HUB_TARGETS = ["taxi_pickups", "bike_starts"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2024)
    ap.add_argument("--month", type=int, default=1)
    ap.add_argument("--test-days", type=int, default=7)
    args = ap.parse_args()
    ym = f"{args.year}-{args.month:02d}"
    ensure_directories()
    tables = REPORTS_DIR / "tables"
    cpath, hpath = tables / f"city_hourly_panel_{ym}.csv", tables / f"hub_hourly_panel_{ym}.csv"
    for f in (cpath, hpath):
        if not f.exists():
            raise SystemExit(f"{f.name} not found. Run: python scripts/build_panel.py --year {args.year} --month {args.month}")
    city = pd.read_csv(cpath, parse_dates=["datetime"])
    hub = pd.read_csv(hpath, parse_dates=["datetime"])

    res, preds = [], {}
    for t in CITY_TARGETS:
        r, p = fc.evaluate(city, t, args.test_days)
        res.append(r)
        preds[t] = p
    city_res = pd.concat(res, ignore_index=True)
    hub_res = pd.concat([fc.hub_evaluation(hub, t, args.test_days) for t in HUB_TARGETS if t in hub.columns], ignore_index=True)

    city_res.to_csv(tables / f"forecast_metrics_{ym}.csv", index=False)
    hub_res.to_csv(tables / f"forecast_hub_metrics_{ym}.csv", index=False)
    fig, axes = plt.subplots(len(preds), 1, figsize=(11, 3.4 * len(preds)), squeeze=False)
    for ax, (t, p) in zip(axes[:, 0], preds.items()):
        ax.plot(p["datetime"], p["actual"], color="black", lw=1.4, label="actual")
        ax.plot(p["datetime"], p["seasonal_naive"], color="#bab0ac", lw=1, label="seasonal naive")
        ax.plot(p["datetime"], p["hour_of_week_weather"], color="#4c78a8", lw=1.4, label="hour-of-week + weather")
        ax.set_title(f"{t}: test period ({ym})", fontsize=10)
        ax.legend(fontsize=8, ncol=3)
        ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / f"forecast_city_{ym}.png", dpi=150)
    plt.close(fig)

    report = REPORTS_DIR / f"day13_forecast_baselines_{ym}.md"
    report.write_text(fc.render_report(ym, city_res, hub_res), encoding="utf-8")
    print(city_res[["target", "model", "mae", "wape_pct", "bias_pct"]].to_string(index=False))
    print(f"\nReport: {report}")


if __name__ == "__main__":
    main()
