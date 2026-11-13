# Data Dictionary

Raw and processed datasets are added from Day 3 onwards. Reference tables that are
committed to the repo are documented below.

## Reference tables (committed in `data/reference/`)

### data_sources_catalog.csv
One row per candidate data source.

| Column | Type | Description |
|--------|------|-------------|
| source_id | string | Unique short ID (e.g. `tlc_trips`) |
| name | string | Human-readable source name |
| category | string | mobility, retail_locations, weather, simulated, ... |
| role | string | What the source is used for in GeoPulse |
| priority | string | primary, primary_fallback, secondary, context, optional |
| granularity | string | trip, point, zone, hour, store_hour, ... |
| file_format | string | parquet, csv, csv_zip, json_geojson |
| access_method | string | direct_download, api, archived_download, generated |
| landing_page | string | Page to verify the dataset and licence |
| url_template | string | Download URL pattern, if known (verify before use) |
| coverage | string | Geographic / time coverage |
| licence | string | Licence or terms |
| attribution_required | string | yes / no |
| status | string | unverified, verified, planned, unavailable |
| last_verified | date | Filled when the source is checked (Day 3 onwards) |

### study_area.json
| Field | Description |
|-------|-------------|
| name | Study area name (Manhattan, New York City) |
| crs | Coordinate system (EPSG:4326, lat/lon) |
| bbox | min_lat, max_lat, min_lon, max_lon (approximate) |
| hubs[] | 10 retail hubs: `hub_id`, `name`, `type`, `lat`, `lon` (approximate centres chosen by the team) |

## Raw / processed datasets

### NYC TLC yellow taxi trips (data/raw/tlc/yellow_tripdata_YYYY-MM.parquet, not committed)
Only these columns are read by `geopulse.ingest_tlc.TRIP_COLUMNS`.

| Column | Type | Description |
|--------|------|-------------|
| tpep_pickup_datetime | datetime | Time the meter was engaged |
| tpep_dropoff_datetime | datetime | Time the meter was disengaged |
| PULocationID | int | Pickup taxi zone ID (see zone lookup) |
| DOLocationID | int | Dropoff taxi zone ID |
| passenger_count | float | Passengers (driver-entered, may be null) |
| trip_distance | float | Trip distance in miles |
| total_amount | float | Total charged to passenger (excludes cash tips) |

### taxi_zone_lookup.csv (data/raw/tlc/, not committed)
| Column | Type | Description |
|--------|------|-------------|
| LocationID | int | Taxi zone ID |
| Borough | string | Borough name (we keep `Manhattan`) |
| Zone | string | Zone name |
| service_zone | string | Yellow Zone / Boro Zone / Airports / EWR |

### reports/tables/tlc_hourly_profile_YYYY-MM.csv (committed, produced by scripts/ingest_tlc.py)
| Column | Type | Description |
|--------|------|-------------|
| PULocationID | int | Manhattan pickup zone |
| Zone | string | Zone name |
| day_type | string | weekday or weekend |
| hour | int | Hour of day (0-23) |
| pickups_total | int | Pickups in that zone/hour/day type over the month |
| days | int | Calendar days of that day type in the month |
| avg_pickups | float | pickups_total / days |

### Cleaning rules (basic_clean)
Rows are dropped when: pickup is outside the target month; duration is <= 0 or > 6 hours;
distance is <= 0 or > 100 miles; total_amount is negative; pickup zone is missing;
or the row is an exact duplicate.

### OpenStreetMap retail POIs (data/interim/osm_pois.csv, not committed)
Source: Overpass API, all `shop=*` plus amenities restaurant, cafe, fast_food, bar, pub, bank, pharmacy, marketplace inside the study-area bounding box. (c) OpenStreetMap contributors, ODbL.

| Column | Type | Description |
|--------|------|-------------|
| osm_type | string | node, way or relation |
| osm_id | int | OSM object ID (unique together with osm_type) |
| lat, lon | float | Location; for ways/relations the centre point |
| name | string | POI name (often missing) |
| shop / amenity | string | Original OSM tag values |
| brand | string | Brand tag if present |
| has_opening_hours | bool | True if an opening_hours tag exists |
| category | string | GeoPulse group: food_beverage, food_retail, fashion, beauty_health, electronics_home, general_gifts, services, other_shop |
| nearest_hub_id | string | Closest retail hub (H01-H10) |
| nearest_hub_m | float | Distance to that hub in metres |

### reports/tables/osm_hub_summary.csv (committed)
One row per hub: `hub_id, hub_name, hub_type, radius_m, poi_total, poi_per_km2, named_share`, then one count column per category. Counts are POIs within `radius_m` (default 500 m) of the hub centre.

### reports/tables/osm_category_counts.csv (committed)
`category, poi_count, named_share, opening_hours_share` - overall POI counts and tag completeness.
