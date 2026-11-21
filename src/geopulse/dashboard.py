"""Day 12: a self-contained HTML dashboard built from the report tables.

One file, no internet and no JavaScript libraries: charts are inline SVG, so the file opens
by double-click and can be sent to a mentor. Every number comes from a committed table.
"""
from __future__ import annotations

from html import escape
from pathlib import Path

import numpy as np
import pandas as pd

from geopulse import multimonth as mm

PALETTE = ["#4c78a8", "#f58518", "#54a24b", "#e45756", "#72b7b2", "#b279a2", "#9d755d", "#bab0ac", "#eeca3b", "#ff9da6"]
W, H, PAD = 560, 230, 34


def fmt(v, spec="{:,.0f}", na="n/a"):
    return na if v is None or (isinstance(v, float) and np.isnan(v)) else spec.format(v)


# ---------- inline SVG helpers ----------
def svg_lines(series: dict[str, list[float]], xlabels: list[str], title: str) -> str:
    """Line chart, x = positions 0..n-1. NaN breaks the line."""
    vals = [v for s in series.values() for v in s if not np.isnan(v)]
    if not vals:
        return f"<p class='muted'>{escape(title)}: no data</p>"
    hi = max(vals) or 1
    n = max(len(s) for s in series.values())
    sx = lambda i: PAD + i * (W - 2 * PAD) / max(n - 1, 1)
    sy = lambda v: H - PAD - v / hi * (H - 2 * PAD)
    out = [f"<svg viewBox='0 0 {W} {H}' role='img' aria-label='{escape(title)}'>",
           f"<text x='{PAD}' y='16' class='t'>{escape(title)}</text>",
           f"<line x1='{PAD}' y1='{H - PAD}' x2='{W - PAD}' y2='{H - PAD}' class='ax'/>"]
    for i in range(0, n, max(1, n // 8)):
        out.append(f"<text x='{sx(i):.1f}' y='{H - PAD + 14}' class='tk' text-anchor='middle'>{escape(str(xlabels[i]))}</text>")
    out.append(f"<text x='{PAD - 4}' y='{sy(hi) + 4:.1f}' class='tk' text-anchor='end'>{fmt(hi)}</text>")
    for k, (name, s) in enumerate(series.items()):
        d, pen = "", False
        for i, v in enumerate(s):
            if np.isnan(v):
                pen = False
                continue
            d += f"{'L' if pen else 'M'}{sx(i):.1f},{sy(v):.1f} "
            pen = True
        out.append(f"<path d='{d}' fill='none' stroke='{PALETTE[k % 10]}' stroke-width='2'><title>{escape(name)}</title></path>")
    out.append("</svg>")
    return "".join(out)


def legend(names: list[str]) -> str:
    return "<p class='lg'>" + " ".join(f"<span><i style='background:{PALETTE[k % 10]}'></i>{escape(n)}</span>"
                                       for k, n in enumerate(names)) + "</p>"


def svg_bars(labels: list[str], values: list[float], title: str, unit: str = "") -> str:
    """Horizontal bars; labels printed on the left, value on the right."""
    if not len(values) or all(np.isnan(values)):
        return f"<p class='muted'>{escape(title)}: no data</p>"
    hi = max(v for v in values if not np.isnan(v)) or 1
    row, left = 22, 170
    h = 28 + row * len(values)
    out = [f"<svg viewBox='0 0 {W} {h}' role='img' aria-label='{escape(title)}'><text x='4' y='16' class='t'>{escape(title)}</text>"]
    for i, (lab, v) in enumerate(zip(labels, values)):
        y = 28 + i * row
        out.append(f"<text x='{left - 6}' y='{y + 12}' class='tk' text-anchor='end'>{escape(str(lab))}</text>")
        if np.isnan(v):
            out.append(f"<text x='{left}' y='{y + 12}' class='tk'>no data</text>")
            continue
        out.append(f"<rect x='{left}' y='{y}' width='{max(v, 0) / hi * (W - left - 70):.1f}' height='16' fill='{PALETTE[0]}'/>")
        out.append(f"<text x='{left + max(v, 0) / hi * (W - left - 70) + 4:.1f}' y='{y + 12}' class='tk'>{fmt(v)}{unit}</text>")
    out.append("</svg>")
    return "".join(out)


def table(headers: list[str], rows: list[list]) -> str:
    h = "".join(f"<th>{escape(x)}</th>" for x in headers)
    b = "".join("<tr>" + "".join(f"<td>{escape(str(c))}</td>" for c in r) + "</tr>" for r in rows)
    return f"<div class='scroll'><table><tr>{h}</tr>{b}</table></div>"


# ---------- sections ----------
def kpi_cards(ov: pd.DataFrame) -> str:
    t, b = ov["taxi_total"].sum(), ov["bike_total"].sum()
    items = [("Months", ", ".join(ov["month"])), ("Taxi pickups", fmt(t)), ("Citi Bike starts (hubs)", fmt(b)),
             ("Bike share of hub trips", fmt(100 * b / (t + b), "{:.1f}%") if t + b else "n/a")]
    return "<div class='kpis'>" + "".join(f"<div class='k'><b>{escape(str(v))}</b><span>{escape(k)}</span></div>" for k, v in items) + "</div>"


def hub_table(stats: pd.DataFrame, metric: str) -> str:
    d = stats[stats["metric"] == metric]
    if d.empty:
        return ""
    g = d.groupby(["hub_name"], sort=False).agg(total=("total", "sum"),
                                                 rhythm=("rhythm", lambda s: s.mode().iloc[0] if len(s) else ""),
                                                 ratio=("weekend_ratio", "mean")).sort_values("total", ascending=False)
    g["rhythm"] = np.where(g["total"] > 0, g["rhythm"], "no data")
    return table(["Hub", f"Total {metric}", "Rhythm", "Weekend / weekday"],
                 [[n, fmt(r.total) if r.total > 0 else "no data", r.rhythm, fmt(r.ratio, "{:.2f}") if r.total > 0 else "n/a"] for n, r in g.iterrows()])


def rhythm_chart(rhythm: pd.DataFrame, metric: str, day_type: str = "weekday", top: int = 5) -> str:
    d = rhythm[(rhythm["metric"] == metric) & (rhythm["day_type"] == day_type)]
    if d.empty:
        return ""
    piv = d.pivot_table(index="hour", columns="hub_name", values="avg", aggfunc="mean").reindex(range(24))
    keep = piv.sum().sort_values(ascending=False).head(top).index
    series = {h: [float(x) for x in piv[h].values] for h in keep}
    return svg_lines(series, [f"{h:02d}" for h in range(24)], f"{metric}: average per hour, {day_type}s, top {len(keep)} hubs") + legend(list(keep))


def weather_section(eff: pd.DataFrame) -> str:
    if eff.empty:
        return ""
    piv = eff.pivot_table(index=["flag", "metric"], columns="month", values="change_pct", aggfunc="first")
    rows = [[f, m] + [fmt(piv.loc[(f, m), c], "{:+.1f}%") for c in piv.columns] for f, m in piv.index]
    return table(["Weather", "Metric"] + list(piv.columns), rows)


def corr_section(corr: pd.DataFrame, top: int = 6) -> str:
    cons = mm.correlation_consistency(corr)
    if cons.empty:
        return ""
    rows = [[r.retail_feature, r.mobility_feature, r.n_months, r.mean_rho, "yes" if r.consistent else "no", r.rho_by_month]
            for r in cons.head(top).itertuples()]
    return table(["Retail feature", "Mobility feature", "Months", "Mean rho", "Consistent", "rho by month"], rows)


CSS = """:root{--bg:#fff;--fg:#1d2330;--mut:#667;--card:#f4f6fa;--line:#d8dde6}
@media(prefers-color-scheme:dark){:root{--bg:#14171d;--fg:#e8ebf1;--mut:#9aa3b2;--card:#1d222b;--line:#323947}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:980px;margin:auto;padding:16px}h1{font-size:1.5rem;margin:.2em 0}h2{font-size:1.1rem;margin-top:1.8em;border-bottom:1px solid var(--line)}
.muted{color:var(--mut)}.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px}
.k{background:var(--card);padding:10px 12px;border-radius:8px}.k b{display:block;font-size:1.2rem}.k span{color:var(--mut);font-size:.8rem}
svg{width:100%;height:auto;max-width:620px}.t{font:600 12px sans-serif;fill:var(--fg)}.tk{font:10px sans-serif;fill:var(--mut)}.ax{stroke:var(--line)}
.lg span{margin-right:12px;font-size:.8rem}.lg i{display:inline-block;width:10px;height:10px;margin-right:4px}
.scroll{overflow-x:auto}table{border-collapse:collapse;font-size:.85rem}th,td{padding:4px 10px;border-bottom:1px solid var(--line);text-align:left}
footer{margin-top:2em;color:var(--mut);font-size:.8rem}"""


def render(months: list[str], tables: Path) -> str:
    """Build the whole page. Sections whose input tables are missing are left out with a note."""
    ov = mm.monthly_overview(tables, months)
    stats, _ = mm.stack(tables, "hub_rhythm_stats_{ym}.csv", months)
    rhythm, _ = mm.stack(tables, "hub_hourly_rhythm_{ym}.csv", months)
    corr, _ = mm.stack(tables, "retail_mobility_correlations_{ym}.csv", months)
    eff, _ = mm.stack(tables, "weather_effect_{ym}.csv", months)
    P = [f"<h1>GeoPulse: Retail Mobility Dashboard</h1><p class='muted'>Manhattan, {escape(months[0])} to {escape(months[-1])}. "
         "Exploratory, descriptive results from public data; not causal.</p>"]
    if ov.empty:
        P.append("<p>No processed months found. Run <code>scripts/run_months.py</code> first.</p>")
    else:
        P.append(kpi_cards(ov))
        if len(ov) > 1:
            P.append("<h2>Month by month</h2>" + svg_bars(list(ov["month"]), [float(x) for x in ov["taxi_per_day"]], "Taxi pickups per day")
                     + svg_bars(list(ov["month"]), [float(x) for x in ov["bike_per_day"]], "Citi Bike starts per day (hubs)"))
    for title, body in (
        ("Hubs: taxi demand and rhythm", hub_table(stats, "taxi_pickups") if len(stats) else ""),
        ("Hubs: Citi Bike demand and rhythm (no data = no station in the catchment)", hub_table(stats, "bike_starts") if len(stats) else ""),
        ("Daily rhythm", (rhythm_chart(rhythm, "taxi_pickups") + rhythm_chart(rhythm, "bike_starts")) if len(rhythm) else ""),
        ("Weather effect: % change in trips in wet / freezing hours", weather_section(eff)),
        ("Retail mix vs mobility: which correlations repeat", corr_section(corr)),
    ):
        P.append(f"<h2>{escape(title)}</h2>" + (body or "<p class='muted'>Not available for these months.</p>"))
    P.append("<footer>Data: NYC TLC, Citi Bike, OpenStreetMap contributors (ODbL), Open-Meteo.com (CC BY 4.0). "
             "Generated by scripts/build_dashboard.py.</footer>")
    return ("<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>GeoPulse Dashboard</title><style>{CSS}</style></head><body><main>{''.join(P)}</main></body></html>")
