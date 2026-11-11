# GeoPulse - Data Sources

This document lists the candidate datasets for GeoPulse, what each one gives us,
how to access it, its limits, and the final decision on how we use it.

> **Note:** Dataset links, schemas and licences change over time. Re-verify each
> source on the day it is ingested (Day 3 onwards) and update the
> "Last verified" column.

---

## 1. Summary Table

| # | Source | Type | Granularity | Role in GeoPulse | Priority |
|---|--------|------|-------------|------------------|----------|
| 1 | NYC TLC Taxi Trip Records | Mobility | Trip level (pickup/dropoff, time, location zone) | Movement/demand around areas | Primary |
| 2 | Citi Bike System Data | Mobility | Trip level (start/end station, time) | Short-distance, hyper-local movement | Primary |
| 3 | OpenStreetMap (OSM) POIs | Retail locations | Point (lat/lon, category) | Store/shop locations, catchment features | Primary |
| 4 | Foursquare Open Source Places | Retail locations | Point (lat/lon, category) | POI enrichment, store categories | Secondary |
| 5 | Google Community Mobility Reports | Mobility trend | Region/day, % change vs baseline | Context only (discontinued) | Context |
| 6 | Synthetic footfall data | Simulated | Store x hour | Store-level footfall, fallback and testing | Primary (fallback) |
| 7 | Weather (Open-Meteo / Meteostat) | Context | Hourly | Weather impact on mobility | Optional |

---

## 2. Source Details

### 2.1 NYC TLC Taxi Trip Records
- **What:** Yellow/Green taxi and for-hire vehicle trips in New York City.
- **Fields (typical):** pickup/dropoff datetime, pickup/dropoff location ID,
  passenger count, trip distance, fare amount.
- **Access:** Published by the NYC Taxi & Limousine Commission on its
  "TLC Trip Record Data" page, as monthly Parquet files. A taxi zone lookup
  table and zone shapefile are provided for mapping location IDs to areas.
- **Use in project:** Hourly pickups/dropoffs per taxi zone as a proxy for
  movement and demand near retail areas.
- **Limits:** Location is a taxi zone, not exact coordinates. Files are large,
  so use one or two months and read only the needed columns.
- **Licence:** Open data (NYC Open Data terms).

### 2.2 Citi Bike System Data
- **What:** Bike-share trips in NYC.
- **Fields (typical):** start/end time, start/end station name, station
  latitude/longitude, rider type.
- **Access:** Published by Citi Bike as monthly downloadable trip history files.
- **Use in project:** Station-level start/end counts give precise coordinates,
  which suits hyper-local analysis near stores.
- **Limits:** Column names have changed across years, so handle both schemas.
  Only covers bike trips.
- **Licence:** Citi Bike data licence agreement (check terms before use).

### 2.3 OpenStreetMap POIs (retail locations)
- **What:** Crowd-sourced map data including shops, cafes, supermarkets,
  malls and transit stops.
- **Fields (typical):** name, lat/lon, tags such as `shop=*`, `amenity=*`.
- **Access:** Overpass API / Overpass Turbo for queries by area and tag,
  or the `osmnx` Python library.
- **Use in project:** Build the store/POI table for a chosen area and extract
  neighbourhood features (number of nearby shops, transit stops).
- **Limits:** Completeness varies by area. No footfall or sales data.
- **Licence:** ODbL. Attribution "(c) OpenStreetMap contributors" is required.

### 2.4 Foursquare Open Source Places
- **What:** Global open dataset of POIs with categories.
- **Fields (typical):** place name, category, lat/lon, address.
- **Access:** Published by Foursquare as an open dataset (hosted on
  Hugging Face / cloud storage). Check Foursquare's site for the current location.
- **Use in project:** Cross-check and enrich OSM POIs, standardise categories.
- **Limits:** Does not include check-in or visit counts. Large, so filter to the
  study area before loading.
- **Licence:** Open licence (verify exact terms at download).
- **Alternative:** The older Foursquare check-in datasets (for example the
  NYC check-in set on Kaggle/academic sites) include real visit timestamps
  and are useful for foot-traffic patterns. Check the licence for academic use.

### 2.5 Google Community Mobility Reports
- **What:** Daily % change in visits to place categories (retail & recreation,
  grocery, parks, transit, workplaces, residential) compared to a pre-pandemic baseline.
- **Status:** **Discontinued.** Google stopped updating it in October 2022, so
  the data covers roughly Feb 2020 to Oct 2022 only. The archived CSV is still
  downloadable.
- **Use in project:** Context only, for example showing how retail mobility
  changed during COVID.
- **Limits:** Aggregated at country/region level, not store level, and
  relative change rather than absolute counts. Cannot be used for hyper-local analysis.
- **Licence:** Google's terms for the report data (check before redistribution).

### 2.6 Synthetic Footfall Data (fallback)
- **Why:** No free source gives real store-level hourly footfall. Synthetic
  data lets us test the full pipeline and build the dashboard.
- **Plan:** Generate hourly visits per store (Day 5) using:
  - Store locations from OSM/Foursquare
  - Hourly patterns by store type (e.g. cafes peak at morning, malls in evening)
  - Weekday/weekend effect, random noise and occasional events
  - Fixed random seed (`RANDOM_SEED = 42`) for reproducibility
- **Fields (planned):** `store_id, store_name, category, lat, lon, timestamp, visits`.
- **Limit:** Patterns are assumptions, not real behaviour. **Always label
  synthetic results clearly in reports and the dashboard.**

### 2.7 Weather (optional context)
- **What:** Hourly temperature, rain and wind.
- **Access:** Open-Meteo (free API, no key) or Meteostat.
- **Use in project:** Analyse how rain/temperature affect mobility and footfall.

---

## 3. Decision

| Need | Chosen source |
|------|---------------|
| Real mobility signal | NYC Taxi + Citi Bike (1-2 recent months) |
| Store / POI locations | OSM (primary), Foursquare (enrichment) |
| Store-level footfall | Synthetic data, anchored to real POIs |
| Historical context | Google Mobility (optional, clearly marked as discontinued) |
| Weather impact | Open-Meteo (optional) |

**Study area:** Manhattan, New York City (dense retail, rich open mobility data).

## 4. Data Quality Risks
- Different coordinate/ID systems (taxi zones vs lat/lon) need a mapping step.
- Schema changes across months/years in Citi Bike files.
- Missing or inconsistent POI categories between OSM and Foursquare.
- Synthetic data may not reflect real behaviour. Keep it separate from real data.
- Large file sizes: use Parquet, column selection and date filters.

## 5. Ethics and Licensing
- Use only open, aggregated data. No personal or individual-level tracking.
- Keep attribution for OSM, TLC, Citi Bike and Foursquare in the final report.
- Do not commit raw data files to GitHub (they are in `.gitignore`).

## 6. Source Tracker

| Source | Link / Page name | Format | Last verified | Status |
|--------|------------------|--------|---------------|--------|
| NYC TLC Trip Records | NYC TLC "TLC Trip Record Data" page | Parquet | _fill on Day 3_ | To do |
| Citi Bike | Citi Bike "System Data" page | CSV/ZIP | _fill on Day 4_ | To do |
| OSM | Overpass API / osmnx | JSON/GeoJSON | _fill on Day 4_ | To do |
| Foursquare OS Places | Foursquare open data page | Parquet | _fill on Day 4_ | To do |
| Google Mobility | Archived CSV (Google) | CSV | _optional_ | Context |
| Synthetic | `generate_synthetic.py` | CSV | Day 5 | Planned |
