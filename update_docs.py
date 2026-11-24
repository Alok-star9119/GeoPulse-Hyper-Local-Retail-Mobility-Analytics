"""Add the missing Day 4-7 lines to README.md and docs/progress_log.md.

Run from the repo root (the folder that contains README.md):
    python update_docs.py
Safe to run more than once: it only adds lines that are not already there.
"""
from pathlib import Path

README = Path("README.md")
LOG = Path("docs/progress_log.md")

RUN_LINES = [
    ("scripts/ingest_osm.py", "python scripts/ingest_osm.py        # Day 4 OpenStreetMap retail POIs (needs internet)"),
    ("scripts/ingest_citibike.py", "python scripts/ingest_citibike.py --year 2024 --month 1   # Day 5 Citi Bike stations (needs internet)"),
    ("scripts/build_panel.py", "python scripts/build_panel.py --year 2024 --month 1   # Day 6 weather + combined hourly tables (needs internet)"),
    ("scripts/quality_review.py", "python scripts/quality_review.py --year 2024 --month 1   # Day 7 data-quality review"),
    ("scripts/map_zones_to_hubs.py", "python scripts/map_zones_to_hubs.py   # Day 8 taxi zones -> hubs (needs internet)"),
    ("scripts/eda_hub_rhythm.py", "python scripts/eda_hub_rhythm.py --year 2024 --month 1   # Day 9 hub rhythm EDA"),
    ("scripts/retail_vs_mobility.py", "python scripts/retail_vs_mobility.py --year 2024 --month 1   # Day 10 retail mix vs mobility"),
    ("scripts/run_months.py", "python scripts/run_months.py --months 2024-02 2024-03   # Day 11 run the monthly pipeline for several months (needs internet)"),
    ("scripts/compare_months.py", "python scripts/compare_months.py   # Day 11 compare months: which findings repeat"),
    ("scripts/build_dashboard.py", "python scripts/build_dashboard.py   # Day 12 single-file HTML dashboard (reports/dashboard.html)"),
    ("scripts/forecast_baseline.py", "python scripts/forecast_baseline.py --year 2024 --month 1   # Day 13 baseline hourly demand forecasts"),
    ("scripts/week2_key_numbers.py", "python scripts/week2_key_numbers.py   # Day 14 headline numbers for the Week 2 summary"),
    ("scripts/check_repo.py", "python scripts/check_repo.py   # Day 15 repository hygiene check (run before committing)"),
]
STATUS = [
    ("Day 4", "- Day 4: retail POI ingestion from OpenStreetMap and hub catchment summary. See [docs/day4_osm_retail_pois.md](docs/day4_osm_retail_pois.md)."),
    ("Day 5", "- Day 5: Citi Bike station activity, hub matching and bike-vs-taxi comparison. See [docs/day5_citibike_stations.md](docs/day5_citibike_stations.md)."),
    ("Day 6", "- Day 6: weather data (Open-Meteo) and combined hourly city/hub datasets with a weather-effect analysis. See [docs/day6_weather_and_panel.md](docs/day6_weather_and_panel.md)."),
    ("Day 7", "- Day 7: automated data-quality review and Week 1 summary. See [docs/week1_summary.md](docs/week1_summary.md)."),
    ("Day 8", "- Day 8: taxi zones mapped to retail hubs; taxi demand added to the hub panel. See [docs/day8_zone_hub_mapping.md](docs/day8_zone_hub_mapping.md)."),
    ("Day 9", "- Day 9: EDA of daily and weekly rhythm per hub (peaks, weekend effect, rhythm labels). See [docs/day9_hub_rhythm_eda.md](docs/day9_hub_rhythm_eda.md)."),
    ("Day 10", "- Day 10: retail mix vs mobility analysis and first notebook. See [docs/day10_retail_vs_mobility.md](docs/day10_retail_vs_mobility.md)."),
    ("Day 11", "- Day 11: multi-month pipeline runner and cross-month comparison (which findings repeat), plus DST-safe weather filling. See [docs/day11_multi_month.md](docs/day11_multi_month.md)."),
    ("Day 12", "- Day 12: offline HTML dashboard (KPIs, hub rhythm, weather effect, repeating correlations). See [docs/day12_dashboard.md](docs/day12_dashboard.md)."),
    ("Day 13", "- Day 13: baseline hourly demand forecasts (seasonal naive, hour-of-week mean, + weather) with a time-ordered test. See [docs/day13_forecast_baselines.md](docs/day13_forecast_baselines.md)."),
    ("Day 14", "- Day 14: Week 2 summary, key-number report and a weather-interpolation quality check. See [docs/week2_summary.md](docs/week2_summary.md)."),
    ("Day 15", "- Day 15: repository hygiene check, Makefile shortcuts and reproducibility guide. See [docs/day15_reproducibility.md](docs/day15_reproducibility.md)."),
]
LOG_ROWS = {
    15: "| 15 | 2026-11-23 | Added a repository hygiene check (forbidden/large files, script docstrings, docs index, gitignore rules), Makefile shortcuts and a reproducibility guide; added a documentation index to the README and ignore rules for zip/PDF files, with tests |",
    14: "| 14 | 2026-11-23 | Added a quality check for interpolated weather hours, a generated key-numbers report (quality, forecast accuracy, cross-month stability) and the Week 2 summary with mentor update draft, with tests |",
    13: "| 13 | 2026-11-21 | Added baseline hourly demand forecasts (seasonal naive, hour-of-week mean, hour-of-week + weather fitted by backfitting) with a time-ordered holdout, city and hub accuracy tables, figure and report, with tests |",
    12: "| 12 | 2026-11-21 | Built a self-contained HTML dashboard (inline SVG, works offline) from the report tables: KPIs, month comparison, hub tables, daily rhythm, weather effect and correlation consistency; fixed a crash on empty correlation tables, with tests |",
    11: "| 11 | 2026-11-20 | Added a multi-month pipeline runner and a cross-month comparison (label, rank, correlation and weather-effect stability), plus DST-safe weather gap filling with a weather_filled flag, with tests |",
    4: "| 4 | 2026-11-12 | Ingested retail POIs from OpenStreetMap (Overpass), categorised them, and built hub catchment summary (500 m) with tests |",
    5: "| 5 | 2026-11-13 | Ingested Citi Bike trips (chunked), built station table, hub matching (500 m), hub hourly profiles and bike-vs-taxi comparison, with tests |",
    6: "| 6 | 2026-11-14 | Added Open-Meteo weather ingestion, combined city-hour and hub-hour datasets (taxi + bike + OSM + weather) and a wet/freezing weather-effect analysis, with tests |",
    10: "| 10 | 2026-11-18 | Related retail mix (category shares, density, diversity) to taxi/bike mobility per hub: trips per 100 POIs, cautious rank correlations with permutation p-values, rhythm-group profiles, report, charts and first Jupyter notebook, with tests |",
    9: "| 9 | 2026-11-18 | EDA of daily and weekly hub rhythm: hourly profiles, weekly heatmaps, peak/daypart statistics, rule-based rhythm labels, profile similarity and busiest/quietest days, with tests |",
    8: "| 8 | 2026-11-15 | Mapped taxi zones to retail hubs (polygon distances, one hub per zone), added taxi pickups to the hub panel, hub taxi-vs-bike summary and a new quality check, with tests |",
    7: "| 7 | 2026-11-15 | Added automated data-quality review (18 checks, outlier flagging, report generation), Week 1 summary and mentor update draft, with tests |",
}
ATTRIBUTION = "Map data (c) OpenStreetMap contributors (ODbL). Weather data by Open-Meteo.com (CC BY 4.0)."


def insert_after_last(lines, prefix, new_line, skip_indented=False):
    idx = max((i for i, l in enumerate(lines) if l.startswith(prefix)), default=None)
    if idx is None:
        lines.append(new_line)
        return
    j = idx + 1
    while skip_indented and j < len(lines) and lines[j].startswith("  "):
        j += 1
    lines.insert(j, new_line)


def main() -> None:
    added = []
    text = README.read_text(encoding="utf-8")
    lines = text.split("\n")

    for key, line in RUN_LINES:
        if key not in text:
            insert_after_last(lines, "python scripts/", line)
            text = "\n".join(lines)
            added.append(f"README run line: {key}")
    for key, line in STATUS:
        if not any(l.startswith(f"- {key}:") for l in lines):
            insert_after_last(lines, "- Day ", line, skip_indented=True)
            added.append(f"README status: {key}")
    text = "\n".join(lines)
    if "Open-Meteo.com" not in text:
        if "Map data (c) OpenStreetMap contributors (ODbL)." in text:
            text = text.replace("Map data (c) OpenStreetMap contributors (ODbL).", ATTRIBUTION)
        else:
            text = text.rstrip("\n") + "\n\n" + ATTRIBUTION + "\n"
        added.append("README attribution")
    README.write_text(text, encoding="utf-8")

    dd = Path("docs/data_dictionary.md")
    if dd.exists() and "hub_feature_table" not in dd.read_text(encoding="utf-8"):
        with open(dd, "a", encoding="utf-8") as f:
            f.write("\n### Day 10 tables\n"
                    "See [day10_retail_vs_mobility.md](day10_retail_vs_mobility.md) for `hub_feature_table_YYYY-MM.csv` "
                    "(retail + mobility features per hub) and `retail_mobility_correlations_YYYY-MM.csv`.\n")
        added.append("data_dictionary: Day 10 pointer")
    if dd.exists() and "hub_rhythm_stats" not in dd.read_text(encoding="utf-8"):
        with open(dd, "a", encoding="utf-8") as f:
            f.write("\n### Day 9 tables\n"
                    "See [day9_hub_rhythm_eda.md](day9_hub_rhythm_eda.md) for `hub_rhythm_stats_YYYY-MM.csv` "
                    "(peaks, dayparts, weekend ratio, rhythm label) and `hub_hourly_rhythm_YYYY-MM.csv`.\n")
        added.append("data_dictionary: Day 9 pointer")
    if dd.exists() and "zone_hub_map.csv" not in dd.read_text(encoding="utf-8"):
        with open(dd, "a", encoding="utf-8") as f:
            f.write("\n### Day 8 tables\n"
                    "See [day8_zone_hub_mapping.md](day8_zone_hub_mapping.md) for `data/reference/zone_hub_map.csv` "
                    "(zone -> hub), `hub_mode_summary_YYYY-MM.csv` and the `taxi_pickups` column of the hub panel.\n")
        added.append("data_dictionary: Day 8 pointer")

    if dd.exists() and "day11_multi_month" not in dd.read_text(encoding="utf-8"):
        with open(dd, "a", encoding="utf-8") as f:
            f.write("\n### Day 11 tables\n"
                    "See [day11_multi_month.md](day11_multi_month.md) for `monthly_overview.csv`, `rhythm_label_stability.csv`, "
                    "`hub_rank_stability.csv`, `correlation_consistency.csv`, `weather_effect_by_month.csv` and `pipeline_run_log.csv`. "
                    "The weather columns also gain `weather_filled` (True if the hour was interpolated, e.g. a daylight-saving gap).\n")
        added.append("data_dictionary: Day 11 pointer")

    text = README.read_text(encoding="utf-8")
    docs = sorted(p.name for p in Path("docs").glob("*.md"))
    missing = [d for d in docs if d not in text]
    if missing:
        if "## Documentation index" not in text:
            text = text.rstrip("\n") + "\n\n## Documentation index\n"
            added.append("README: documentation index heading")
        text = text.rstrip("\n") + "\n" + "\n".join(f"- [docs/{d}](docs/{d})" for d in missing) + "\n"
        added += [f"README doc link: {d}" for d in missing]
        README.write_text(text, encoding="utf-8")

    gi = Path(".gitignore")
    if gi.exists():
        have = {l.strip() for l in gi.read_text(encoding="utf-8").splitlines()}
        need = [r for r in ("*.zip", "/*.pdf") if r not in have]
        if need:
            with open(gi, "a", encoding="utf-8") as f:
                f.write("\n# Archives and assignment PDFs must not be committed\n" + "\n".join(need) + "\n")
            added += [f".gitignore rule: {r}" for r in need]

    log = LOG.read_text(encoding="utf-8").rstrip("\n").split("\n")
    for day, row in sorted(LOG_ROWS.items()):
        if not any(l.startswith(f"| {day} |") for l in log):
            log.append(row)
            added.append(f"progress_log: Day {day}")
    LOG.write_text("\n".join(log) + "\n", encoding="utf-8")

    print("Added:" if added else "Nothing to add, everything is already there.")
    for a in added:
        print("  +", a)


if __name__ == "__main__":
    main()
