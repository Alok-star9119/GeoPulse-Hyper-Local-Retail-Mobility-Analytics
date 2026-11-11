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
_To be filled as datasets are added (Day 3 onwards)._

| Dataset | Column | Type | Description |
|---------|--------|------|-------------|
