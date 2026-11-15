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
]
STATUS = [
    ("Day 4", "- Day 4: retail POI ingestion from OpenStreetMap and hub catchment summary. See [docs/day4_osm_retail_pois.md](docs/day4_osm_retail_pois.md)."),
    ("Day 5", "- Day 5: Citi Bike station activity, hub matching and bike-vs-taxi comparison. See [docs/day5_citibike_stations.md](docs/day5_citibike_stations.md)."),
    ("Day 6", "- Day 6: weather data (Open-Meteo) and combined hourly city/hub datasets with a weather-effect analysis. See [docs/day6_weather_and_panel.md](docs/day6_weather_and_panel.md)."),
    ("Day 7", "- Day 7: automated data-quality review and Week 1 summary. See [docs/week1_summary.md](docs/week1_summary.md)."),
]
LOG_ROWS = {
    4: "| 4 | 2026-11-12 | Ingested retail POIs from OpenStreetMap (Overpass), categorised them, and built hub catchment summary (500 m) with tests |",
    5: "| 5 | 2026-11-13 | Ingested Citi Bike trips (chunked), built station table, hub matching (500 m), hub hourly profiles and bike-vs-taxi comparison, with tests |",
    6: "| 6 | 2026-11-14 | Added Open-Meteo weather ingestion, combined city-hour and hub-hour datasets (taxi + bike + OSM + weather) and a wet/freezing weather-effect analysis, with tests |",
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

    log = LOG.read_text(encoding="utf-8").rstrip("\n").split("\n")
    for day, row in LOG_ROWS.items():
        if not any(l.startswith(f"| {day} |") for l in log):
            log.append(row)
            added.append(f"progress_log: Day {day}")
    LOG.write_text("\n".join(log) + "\n", encoding="utf-8")

    print("Added:" if added else "Nothing to add, everything is already there.")
    for a in added:
        print("  +", a)


if __name__ == "__main__":
    main()
