"""Day 9: exploratory analysis of daily and weekly rhythm per retail hub.

Run after scripts/build_panel.py (and Day 8's map_zones_to_hubs.py for taxi by hub):
  python scripts/eda_hub_rhythm.py --year 2024 --month 1

Outputs (committed)
  reports/tables/hub_rhythm_stats_YYYY-MM.csv        one row per hub x metric, with rhythm label
  reports/tables/hub_hourly_rhythm_YYYY-MM.csv       hub x metric x day type x hour (avg, share)
  reports/tables/city_weekly_heatmap_YYYY-MM.csv     day-of-week x hour averages (city level)
  reports/tables/hub_profile_similarity_YYYY-MM.csv  hub x hub correlation of weekday profiles
  reports/tables/daily_extremes_YYYY-MM.csv          busiest / quietest days with weather
  reports/day9_hub_rhythm_YYYY-MM.md                 readable report
  reports/figures/hub_rhythm_<metric>_YYYY-MM.png    weekday vs weekend profile per hub
  reports/figures/hub_dayparts_<metric>_YYYY-MM.png  share of volume by daypart per hub
  reports/figures/weekly_heatmap_YYYY-MM.png         city day-of-week x hour heatmaps
"""
import argparse

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from geopulse import eda
from geopulse.config import FIGURES_DIR, REPORTS_DIR, ensure_directories

NICE = {"taxi_pickups": "Taxi pickups", "bike_starts": "Bike starts", "bike_starts_hubs": "Bike starts (near hubs)"}
COLORS = {"weekday": "#1b4f72", "weekend": "#d95f02"}


def plot_small_multiples(rhythm: pd.DataFrame, metric: str, ym: str) -> None:
    hubs = rhythm[["hub_id", "hub_name"]].drop_duplicates().values.tolist()
    ncols = 2
    nrows = int(np.ceil(len(hubs) / ncols))
    fig, axs = plt.subplots(nrows, ncols, figsize=(11, 2.3 * nrows), sharex=True, sharey=True)
    for ax, (hid, name) in zip(axs.ravel(), hubs):
        g = rhythm[rhythm["hub_id"] == hid]
        if g["share"].isna().all():
            ax.text(0.5, 0.5, "no data", ha="center", va="center", transform=ax.transAxes, color="grey")
        for dt, style in (("weekday", "-"), ("weekend", "--")):
            s = g[g["day_type"] == dt].sort_values("hour")
            ax.plot(s["hour"], s["share"] * 100, style, color=COLORS[dt], label=dt)
        ax.set_title(name, fontsize=9)
        ax.grid(alpha=0.3)
    for ax in axs.ravel()[len(hubs):]:
        ax.set_visible(False)
    for i, ax in enumerate(axs.ravel()[:len(hubs)]):          # hour labels on the last visible panel of each column
        if i + ncols >= len(hubs):
            ax.tick_params(labelbottom=True)
    axs.ravel()[0].legend(fontsize=8)
    fig.supxlabel("Hour of day")
    fig.supylabel("% of the day's volume")
    fig.suptitle(f"{NICE[metric]}: daily rhythm per hub, {ym}", y=1.0)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / f"hub_rhythm_{metric}_{ym}.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_dayparts(hub: pd.DataFrame, stats: pd.DataFrame, metric: str, ym: str) -> None:
    cols = [c for c in stats.columns if c.startswith("share_")]
    d = stats[stats["total"] > 0].set_index("hub_name")[cols] * 100
    if d.empty:
        return
    d.columns = [c.replace("share_", "") for c in d.columns]
    d = d.loc[d.sum(axis=1).index[::-1]]
    ax = d.plot(kind="barh", stacked=True, figsize=(9, 5), colormap="viridis")
    ax.set_xlabel("% of weekday volume")
    ax.set_ylabel("")
    ax.set_title(f"{NICE[metric]}: weekday volume by time of day, {ym}")
    ax.legend(fontsize=8, ncol=5, loc="upper center", bbox_to_anchor=(0.5, -0.12))
    ax.figure.savefig(FIGURES_DIR / f"hub_dayparts_{metric}_{ym}.png", dpi=150, bbox_inches="tight")
    plt.close(ax.figure)


def plot_heatmaps(city: pd.DataFrame, metrics: list, ym: str) -> pd.DataFrame:
    fig, axs = plt.subplots(1, len(metrics), figsize=(6.5 * len(metrics), 3.6), squeeze=False)
    long = []
    for ax, m in zip(axs[0], metrics):
        h = eda.weekly_heatmap(city, m)
        im = ax.imshow(h.values, aspect="auto", cmap="YlOrRd")
        ax.set_yticks(range(7), h.index)
        ax.set_xticks(range(0, 24, 3))
        ax.set_xlabel("Hour of day")
        ax.set_title(f"{NICE.get(m, m)} (average per hour)", fontsize=10)
        fig.colorbar(im, ax=ax, shrink=0.8)
        long.append(h.reset_index(names="day").assign(metric=m))
    fig.suptitle(f"Weekly rhythm, Manhattan, {ym}")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / f"weekly_heatmap_{ym}.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    return pd.concat(long, ignore_index=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2024)
    ap.add_argument("--month", type=int, default=1)
    args = ap.parse_args()
    ym = f"{args.year}-{args.month:02d}"

    ensure_directories()
    tables = REPORTS_DIR / "tables"
    hub_path, city_path = tables / f"hub_hourly_panel_{ym}.csv", tables / f"city_hourly_panel_{ym}.csv"
    for f in (hub_path, city_path):
        if not f.exists():
            raise SystemExit(f"{f.name} not found. Run scripts/build_panel.py --year {args.year} --month {args.month} first.")
    hub = pd.read_csv(hub_path, parse_dates=["datetime"])
    city = pd.read_csv(city_path, parse_dates=["datetime"])

    metrics = eda.available_metrics(hub)
    if "taxi_pickups" not in metrics:
        print("Note: hub panel has no taxi_pickups. Run scripts/map_zones_to_hubs.py and build_panel.py to add it.")
    print("Metrics:", metrics)

    stats, rhythms, extremes = [], [], []
    for m in metrics:
        r = eda.hourly_rhythm(hub, m)
        s = eda.hub_rhythm_stats(hub, m)
        rhythms.append(r)
        stats.append(s)
        plot_small_multiples(r, m, ym)
        plot_dayparts(hub, s, m, ym)
    stats = pd.concat(stats, ignore_index=True)
    rhythm = pd.concat(rhythms, ignore_index=True)
    stats.to_csv(tables / f"hub_rhythm_stats_{ym}.csv", index=False)
    rhythm.to_csv(tables / f"hub_hourly_rhythm_{ym}.csv", index=False)

    sim_metric = "taxi_pickups" if "taxi_pickups" in metrics else metrics[0]
    eda.profile_similarity(rhythm[rhythm["metric"] == sim_metric]).to_csv(
        tables / f"hub_profile_similarity_{ym}.csv")

    city_metrics = [m for m in ("taxi_pickups", "bike_starts_hubs") if m in city.columns]
    plot_heatmaps(city, city_metrics, ym).to_csv(tables / f"city_weekly_heatmap_{ym}.csv", index=False)
    ext = pd.concat([eda.daily_extremes(city, m) for m in city_metrics], ignore_index=True)
    ext.to_csv(tables / f"daily_extremes_{ym}.csv", index=False)

    (REPORTS_DIR / f"day9_hub_rhythm_{ym}.md").write_text(eda.render_report(stats, ext, ym), encoding="utf-8")
    show = ["metric", "hub_name", "total", "weekday_peak_hour", "weekend_ratio", "rhythm"]
    print(stats[[c for c in show if c in stats.columns]].to_string(index=False))
    print(f"\nReport: reports/day9_hub_rhythm_{ym}.md")


if __name__ == "__main__":
    main()
