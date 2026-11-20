"""Day 11: compare all processed months and show which findings repeat.

Usage
  python scripts/compare_months.py                    # use every month found in reports/tables
  python scripts/compare_months.py --months 2024-01 2024-02 2024-03

Reads the per-month tables from Days 5-10 (run `python scripts/run_months.py` first).
Needs at least 2 months. Output (committed):
  reports/tables/monthly_overview.csv, rhythm_label_stability.csv, hub_rank_stability.csv,
  correlation_consistency.csv, weather_effect_by_month.csv
  reports/figures/day11_monthly_overview.png, day11_hub_volume_by_month.png, day11_correlation_consistency.png
  reports/day11_multi_month_comparison.md
"""
import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from geopulse import multimonth as mm
from geopulse.config import REPORTS_DIR, ensure_directories


def fig_overview(ov, path):
    fig, ax = plt.subplots(1, 3, figsize=(11, 3.6))
    x = np.arange(len(ov))
    for a, col, title in zip(ax, ["taxi_per_day", "bike_per_day", "temp_mean_c"],
                             ["Taxi pickups per day", "Citi Bike starts per day (hubs)", "Mean temperature (C)"]):
        a.bar(x, ov[col], color="#4c78a8")
        a.set_xticks(x, ov["month"], rotation=30)
        a.set_title(title, fontsize=10)
        a.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_hub_volume(stats, path):
    d = stats.assign(per_day=lambda d: d["total"].where(d["total"] > 0))
    metrics = list(d["metric"].unique())
    fig, axes = plt.subplots(1, len(metrics), figsize=(5.5 * len(metrics), 4.2), squeeze=False)
    for a, metric in zip(axes[0], metrics):
        piv = d[d.metric == metric].pivot(index="hub_name", columns="month", values="per_day")
        piv = piv.loc[piv.mean(axis=1).sort_values().index]
        w = 0.8 / len(piv.columns)
        for i, m in enumerate(piv.columns):
            a.barh(np.arange(len(piv)) + i * w, piv[m], height=w, label=m)
        a.set_yticks(np.arange(len(piv)) + 0.4 - w / 2, piv.index, fontsize=8)
        a.set_title(f"{metric}: monthly total by hub", fontsize=10)
        a.legend(fontsize=8)
        a.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_corr(corr, path):
    d = corr[corr.n_months >= 2].head(12).iloc[::-1]
    if d.empty:
        return False
    fig, ax = plt.subplots(figsize=(8, 0.45 * len(d) + 1.5))
    for y, r in enumerate(d.itertuples()):
        vals = [float(p.split("=")[1]) for p in r.rho_by_month.split("; ")]
        ax.plot([min(vals), max(vals)], [y, y], color="#999", lw=2, zorder=1)
        ax.scatter(vals, [y] * len(vals), color="#4c78a8" if r.consistent else "#e45756", zorder=2)
    ax.set_yticks(range(len(d)), [f"{r.retail_feature} vs {r.mobility_feature}" for r in d.itertuples()], fontsize=8)
    ax.axvline(0, color="black", lw=0.8)
    ax.set_xlabel("Spearman rho, one dot per month (blue = consistent, red = not)")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", nargs="+")
    ap.add_argument("--tables-dir", type=Path, default=REPORTS_DIR / "tables")
    ap.add_argument("--out-dir", type=Path, default=REPORTS_DIR)
    args = ap.parse_args()

    ensure_directories()
    tables, out = args.tables_dir, args.out_dir
    (out / "figures").mkdir(parents=True, exist_ok=True)
    (out / "tables").mkdir(parents=True, exist_ok=True)
    months = sorted(set(args.months)) if args.months else mm.discover_months(tables, "city_hourly_panel_{ym}.csv")
    if len(months) < 2:
        raise SystemExit(f"Need at least 2 months, found {months}. Run: python scripts/run_months.py --months 2024-02 2024-03")

    stats, m1 = mm.stack(tables, "hub_rhythm_stats_{ym}.csv", months)
    corr, m2 = mm.stack(tables, "retail_mobility_correlations_{ym}.csv", months)
    eff, m3 = mm.stack(tables, "weather_effect_{ym}.csv", months)
    for name, found in (("hub_rhythm_stats", m1), ("retail_mobility_correlations", m2), ("weather_effect", m3)):
        gap = sorted(set(months) - set(found))
        if gap:
            print(f"Note: {name} missing for {', '.join(gap)}")

    ov = mm.monthly_overview(tables, months)
    labels, ranks = mm.label_stability(stats), mm.rank_stability(stats)
    cons = mm.correlation_consistency(corr)
    wtab, sens = mm.weather_effect_table(eff), mm.sensitivity_consistency(eff)

    t = out / "tables"
    ov.to_csv(t / "monthly_overview.csv", index=False)
    labels.to_csv(t / "rhythm_label_stability.csv", index=False)
    ranks.to_csv(t / "hub_rank_stability.csv", index=False)
    cons.to_csv(t / "correlation_consistency.csv", index=False)
    wtab.to_csv(t / "weather_effect_by_month.csv", index=False)

    fig_overview(ov, out / "figures" / "day11_monthly_overview.png")
    fig_hub_volume(stats, out / "figures" / "day11_hub_volume_by_month.png")
    fig_corr(cons, out / "figures" / "day11_correlation_consistency.png")

    report = out / "day11_multi_month_comparison.md"
    report.write_text(mm.render_report(months, ov, labels, ranks, cons, wtab, sens), encoding="utf-8")
    print(f"Compared {len(months)} months: {', '.join(months)}")
    print(f"Report: {report}")
    print("Now read the report and write your own Findings in docs/day11_multi_month.md")


if __name__ == "__main__":
    main()
