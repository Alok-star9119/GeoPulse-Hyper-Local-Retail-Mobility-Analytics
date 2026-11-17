# Day 8 - Mapping Taxi Zones to Retail Hubs

## Goal
Until now taxi demand was only available for all of Manhattan, while bikes and shops were
available per hub. Day 8 assigns taxi zones to hubs so all three can be compared side by side
in the hub panel (the first Week 2 cleaning/integration step).

## Method
1. Download the TLC taxi-zone polygons and keep Manhattan zones (one row per `LocationID`).
2. Project to metres (UTM 18N) and measure, for every zone and hub:
   - the distance from the hub centre to the zone **boundary** (0 if the hub is inside the zone)
   - the distance from the hub centre to the zone **centroid**
3. Assign each zone to the hub with the smallest boundary distance (ties: smallest centroid distance).
4. Keep the assignment only if the distance is <= 500 m (changeable with `--radius`);
   other zones stay unassigned and are not counted for any hub.
5. Each zone belongs to **at most one hub**, so no taxi pickup is counted twice.
6. Aggregate cleaned taxi pickups (Day 3) by hub and hour, and add them to the hub panel.
7. Summarise each hub: taxi vs bike volume, hourly correlation, weekday peak hours.

## Run
```bash
source .venv/bin/activate
pytest -q                                  # geometry tests now run (they were skipped before geopandas)
python scripts/map_zones_to_hubs.py        # or: --shapes <your downloaded taxi_zones.zip>
python scripts/build_panel.py --year 2024 --month 1
python scripts/quality_review.py --year 2024 --month 1
```

## Outputs
| File | Committed? |
|------|-----------|
| data/raw/tlc/taxi_zones.zip | No |
| data/reference/zone_hub_map.csv | Yes |
| reports/tables/zone_hub_coverage.csv | Yes |
| reports/figures/zones_hub_map.png | Yes |
| reports/tables/hub_hourly_panel_YYYY-MM.csv (now has `taxi_pickups`) | Yes |
| reports/tables/hub_mode_summary_YYYY-MM.csv | Yes |
| reports/figures/hub_taxi_vs_bike_YYYY-MM.png | Yes |
| data/reference/data_sources_catalog.csv (new row `tlc_zone_shapes`) | Yes |

## Data dictionary
### data/reference/zone_hub_map.csv
| Column | Description |
|--------|-------------|
| LocationID, zone | TLC taxi zone ID and name |
| hub_id | Assigned hub (empty if no hub within the radius) |
| nearest_hub_id | Closest hub regardless of radius |
| hub_distance_m | Distance hub centre -> zone boundary (m), 0 if inside |
| centroid_distance_m | Distance hub centre -> zone centroid (m) |
| contains_hub | True if the hub lies inside the zone |

### hub_mode_summary_YYYY-MM.csv
| Column | Description |
|--------|-------------|
| taxi_pickups, bike_starts | Monthly totals in the hub catchment |
| taxi_share | taxi / (taxi + bike); a relative mix indicator only |
| hourly_corr_taxi_bike | Correlation of hourly taxi and bike counts at that hub |
| weekday_peak_hour_taxi / _bike | Hour with the highest average weekday volume |

## Findings
_Fill in after running: how many zones were assigned; which hubs got no zone (see
zone_hub_coverage.csv); which hubs are taxi-dominant vs bike-dominant; whether peak hours differ._

## Limitations
- Taxi zones are large and irregular. A zone assigned to a hub may extend well beyond 500 m, so
  taxi counts cover a bigger area than bike counts (docks within 500 m).
- If two hubs fall in the same zone only one receives it; the other may show no taxi data.
- Hub centres are approximate. Pickups are trip starts, not footfall.
- Only yellow taxis are included (no green taxis or app-based rides).
