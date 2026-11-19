"""Day 10: relate the retail mix around each hub to its taxi/bike mobility.

Run after Day 4 (ingest_osm.py) and Day 9 (eda_hub_rhythm.py), same month:
  python scripts/retail_vs_mobility.py --year 2024 --month 1

Outputs (committed)
  reports/tables/hub_feature_table_YYYY-MM.csv            retail + mobility features per hub
  reports/tables/retail_mobility_correlations_YYYY-MM.csv Spearman rho, n hubs, permutation p
  reports/tables/rhythm_group_summary_YYYY-MM.csv         average retail profile per rhythm label
  reports/day10_retail_vs_mobility_YYYY-MM.md             readable report
  reports/figures/retail_mix_heatmap_YYYY-MM.png          category shares per hub
  reports/figures/poi_density_vs_trips_YYYY-MM.png        retail density vs taxi / bike volume
  reports/figures/trips_per_poi_YYYY-MM.png               trips per 100 POIs per hub
"""
import argparse

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from geopulse import retail_mobility as rm
from geopulse.config import FIGURES_DIR, REPORTS_DIR, ensure_directories


def plot_heatmap(f: pd.DataFrame, ym: str) -> None:
    share_cols = [c for c in f.columns if c.startswith("share_")]
    d = f.sort_values("poi_total").set_index("hub_name")[share_cols] * 100
    d.columns = [c.replace("share_", "") for c in d.columns]
    fig, ax = plt.subplots(figsize=(8, 5.5))
    im = ax.imshow(d.fillna(0).values, aspect="auto", cmap="Blues", vmin=0)
    ax.set_xticks(range(d.shape[1]), d.columns, rotation=35, ha="right")
    ax.set_yticks(range(d.shape[0]), d.index)
    for i in range(d.shape[0]):
        for j in range(d.shape[1]):
            v = d.iloc[i, j]
            if pd.notna(v):
                ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=8,
                        color="white" if v > 0.6 * np.nanmax(d.values) else "black")
    fig.colorbar(im, ax=ax, label="% of the hub's POIs")
    ax.set_title(f"Retail mix around each hub (OpenStreetMap), {ym}")
    fig.savefig(FIGURES_DIR / f"retail_mix_heatmap_{ym}.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_scatter(f: pd.DataFrame, ym: str) -> None:
    pres = [p for p in ("taxi", "bike") if f"{p}_total" in f.columns and f[f"{p}_total"].notna().sum() >= 3]
    if not pres:
        return
    fig, axs = plt.subplots(1, len(pres), figsize=(6 * len(pres), 4.8), squeeze=False)
    for ax, pre in zip(axs[0], pres):
        d = f.dropna(subset=[f"{pre}_total"])
        ax.scatter(d["poi_per_km2"], d[f"{pre}_total"], color="#1b4f72")
        for r in d.itertuples():
            ax.annotate(r.hub_name.split(" (")[0], (r.poi_per_km2, getattr(r, f"{pre}_total")),
                        xytext=(4, 3), textcoords="offset points", fontsize=7)
        rho, n, p = rm.spearman(d["poi_per_km2"], d[f"{pre}_total"])
        ax.set_yscale("log")
        ax.set_xlabel("POIs per km2 (OpenStreetMap)")
        ax.set_ylabel(f"{pre} trips in the month (log scale)")
        ptxt = "p < 0.001" if p < 0.001 else f"p = {p:.3f}"
        ax.set_title(f"{pre.title()}: rho = {rho:.2f}, n = {n}, {ptxt}", fontsize=10)
        ax.grid(alpha=0.3)
    fig.suptitle(f"Retail density vs mobility volume, {ym} (exploratory)")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / f"poi_density_vs_trips_{ym}.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_trips_per_poi(f: pd.DataFrame, ym: str) -> None:
    cols = [c for c in ("taxi_per_100_poi", "bike_per_100_poi") if c in f.columns and f[c].notna().any()]
    if not cols:
        return
    d = f.set_index("hub_name")[cols].dropna(how="all")
    d = d.loc[d.max(axis=1).sort_values().index]
    ax = d.rename(columns=lambda c: c.split("_")[0]).plot(kind="barh", figsize=(8.5, 5.5),
                                                          color=["#1b4f72", "#d95f02"][:len(cols)])
    ax.set_xlabel("Trips in the month per 100 POIs")
    ax.set_ylabel("")
    ax.set_title(f"Mobility relative to retail supply, {ym} (rough index)")
    ax.figure.savefig(FIGURES_DIR / f"trips_per_poi_{ym}.png", dpi=150, bbox_inches="tight")
    plt.close(ax.figure)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2024)
    ap.add_argument("--month", type=int, default=1)
    args = ap.parse_args()
    ym = f"{args.year}-{args.month:02d}"

    ensure_directories()
    tables = REPORTS_DIR / "tables"
    need = {"osm_hub_summary.csv": "scripts/ingest_osm.py",
            f"hub_rhythm_stats_{ym}.csv": f"scripts/eda_hub_rhythm.py --year {args.year} --month {args.month}"}
    for name, how in need.items():
        if not (tables / name).exists():
            raise SystemExit(f"{name} not found. Run {how} first.")
    osm = pd.read_csv(tables / "osm_hub_summary.csv")
    stats = pd.read_csv(tables / f"hub_rhythm_stats_{ym}.csv")

    f = rm.hub_feature_table(osm, stats)
    f.to_csv(tables / f"hub_feature_table_{ym}.csv", index=False)

    x_cols, y_cols = rm.default_columns(f)
    corr = rm.correlation_table(f, x_cols, y_cols)
    corr.to_csv(tables / f"retail_mobility_correlations_{ym}.csv", index=False)

    groups = [rm.rhythm_group_summary(f, c).rename(columns={c: "rhythm"}).assign(source=c.split("_")[0])
              for c in ("taxi_rhythm", "bike_rhythm") if c in f.columns]
    if groups:
        pd.concat(groups, ignore_index=True).to_csv(tables / f"rhythm_group_summary_{ym}.csv", index=False)

    (REPORTS_DIR / f"day10_retail_vs_mobility_{ym}.md").write_text(rm.render_report(f, corr, ym), encoding="utf-8")
    plot_heatmap(f, ym)
    plot_scatter(f, ym)
    plot_trips_per_poi(f, ym)

    print(f"{len(f)} hubs; {int(corr['rho'].notna().sum())} correlations computed")
    print(corr.dropna(subset=["rho"]).head(8).to_string(index=False))
    print(f"\nReport: reports/day10_retail_vs_mobility_{ym}.md")


if __name__ == "__main__":
    main()
