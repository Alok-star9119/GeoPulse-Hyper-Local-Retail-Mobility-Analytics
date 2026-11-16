# Week 1 Summary - Setup, Data Sourcing and Ingestion

**Project:** GeoPulse - Hyper-Local Retail Mobility Analytics (Manhattan, NYC)
**Period:** Day 1 - Day 7

## What was delivered
| Day | Deliverable | Key files |
|-----|-------------|-----------|
| 1 | Repository, structure, config, logging, project plan | `src/geopulse/config.py`, `docs/project_plan.md` |
| 2 | Source research, machine-readable catalog, study area (10 retail hubs) | `data/reference/`, `docs/data_sources.md` |
| 3 | NYC TLC taxi ingestion: validate, clean, Manhattan filter, hourly profile | `src/geopulse/ingest_tlc.py` |
| 4 | OpenStreetMap retail POIs, 8 categories, 500 m hub catchments | `src/geopulse/ingest_osm.py` |
| 5 | Citi Bike station activity, hub matching, bike-vs-taxi comparison | `src/geopulse/ingest_citibike.py` |
| 6 | Weather (Open-Meteo), combined city-hour and hub-hour datasets, weather effect | `src/geopulse/ingest_weather.py`, `panel.py` |
| 7 | Automated data-quality review and report | `src/geopulse/quality.py`, `scripts/quality_review.py` |

## Data assets at the end of Week 1
| Source | What it gives | Granularity |
|--------|---------------|-------------|
| NYC TLC yellow taxi | Movement demand | trip -> hour x zone |
| Citi Bike | Hyper-local movement | trip -> station -> hub x hour |
| OpenStreetMap | Retail mix around each hub | point -> hub |
| Open-Meteo | Temperature, rain, snow, wind | hour |

Combined outputs: `city_hourly_panel` (one row per hour) and `hub_hourly_panel` (one row per hub-hour).

## Engineering practices used
- Reusable package (`src/geopulse`) with scripts on top, so every step is repeatable with one command.
- Unit tests for each module (run with `pytest`); synthetic fixtures, no real data needed.
- Large raw files are git-ignored; small result tables and figures are committed.
- Every source documented with licence and attribution; limitations written down per day.

## Key results (fill in from your outputs)
- Rows kept after cleaning: taxi ___ (___ % removed), bikes ___ (___ % removed)
- Busiest hub by bike trips: ___ ; highest casual (tourist-like) share: ___
- Taxi vs bike weekday hourly correlation: ___
- Trips change when wet: taxi ___ %, bike ___ %
- Data-quality review: ___ PASS, ___ WARN, ___ FAIL (see `reports/week1_data_quality_report_YYYY-MM.md`)

## Known limitations
- One month of data (January 2024) is a small and seasonal sample.
- Taxi data is city-wide; taxi zones are not yet mapped to hubs.
- Several hubs have no Citi Bike stations within 500 m.
- Weather effect is descriptive, not causal.

## Plan for Week 2 (proposed): Cleaning, validation, EDA
| Day | Focus |
|-----|-------|
| 8 | Map taxi zones to hubs (zone polygons) so taxi data enters the hub panel |
| 9 | EDA: daily and weekly rhythm of footfall per hub |
| 10 | EDA: weekday vs weekend, holidays and unusual days |
| 11 | EDA: retail mix vs mobility (which hub types attract which patterns) |
| 12 | Extend to more months to reduce seasonality bias |
| 13 | Hub profiling / clustering |
| 14 | EDA notebook, week 2 review |

---

## Draft progress update to mentor (edit the numbers before sending)
**Subject:** GeoPulse - Week 1 progress update

Hello <Mentor name>,

I have completed Week 1 of the GeoPulse project (hyper-local retail mobility analytics for Manhattan).

- Sourced and ingested four datasets: NYC TLC taxi trips, Citi Bike trips, OpenStreetMap retail POIs and Open-Meteo weather.
- Cleaned and validated each source with documented rules, and combined them into hourly city-level and hub-level datasets.
- Added an automated data-quality review (___ checks; ___ passed, ___ warnings, ___ failures) and unit tests for every module.
- Early finding: ___ (for example, trips fall by ___ % in wet hours, bikes more than taxis).

Next week I will move to cleaning refinements and exploratory analysis, including mapping taxi zones to retail hubs.
The code and documentation are in my repository: <GitHub link>.

Regards,
<Your name>
