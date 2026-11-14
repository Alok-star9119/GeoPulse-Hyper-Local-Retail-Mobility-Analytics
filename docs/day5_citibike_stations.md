# Day 5 - Citi Bike Station Activity

## Goal
Add the most hyper-local movement source: bike trip starts at individual docking stations.
Match stations to the 10 retail hubs and compare the hourly rhythm of bikes with Day 3's taxis.

## Steps
1. Download one monthly Citi Bike file (zip with one or more CSVs).
2. Stream it in chunks (files have millions of rows) and read only 7 columns.
3. Clean: parse times; drop trips shorter than 60 s or longer than 24 h; drop rows without a
   station, outside the target month or outside the Manhattan bounding box.
4. Reduce to station x date x hour x user-type counts while streaming (small and fast).
5. Build a station table (location, trips, casual share) and assign each station to the nearest
   hub if it is within 500 m.
6. Build hub-level hourly profiles (average starts per hour, weekday/weekend) and summary.
7. Compare normalised weekday hourly shares of bikes and taxis (Pearson correlation).

## Run
```bash
source .venv/bin/activate
python scripts/ingest_tlc.py --year 2024 --month 1        # Day 3, needed for the comparison
python scripts/ingest_citibike.py --year 2024 --month 1
```
The script tries two known file-name patterns. If both fail, open
https://s3.amazonaws.com/tripdata/index.html , copy the link of the file for your month and run
`--url <link>`, or download it yourself and use `--file <path>`. Keep the same year/month as Day 3.

## Outputs
| File | Committed? |
|------|-----------|
| data/raw/citibike/* | No (large) |
| reports/tables/citibike_quality_YYYY-MM.json | Yes |
| reports/tables/citibike_station_summary_YYYY-MM.csv | Yes |
| reports/tables/citibike_hub_summary_YYYY-MM.csv | Yes |
| reports/tables/citibike_hub_hourly_YYYY-MM.csv | Yes |
| reports/tables/bike_vs_taxi_hourly_YYYY-MM.csv | Yes (needs Day 3 table) |
| reports/figures/citibike_hub_trips_YYYY-MM.png | Yes |
| reports/figures/citibike_vs_taxi_hourly_YYYY-MM.png | Yes (needs Day 3 table) |

## Data dictionary
### Source columns read from Citi Bike
| Column | Description |
|--------|-------------|
| started_at / ended_at | Trip start / end time |
| start_station_id / start_station_name | Docking station of the trip start |
| start_lat / start_lng | Station coordinates |
| member_casual | member (subscriber) or casual (single-ride / day pass) |
Older files (before 2021) use different names; they are renamed automatically.

### citibike_station_summary_YYYY-MM.csv
| Column | Description |
|--------|-------------|
| station_id, station_name | Station |
| trips | Trip starts in the month |
| lat, lon | Mean start coordinates |
| casual_share | Share of trips by casual riders |
| nearest_hub_id, nearest_hub_m | Closest hub and distance in metres |
| hub_id | Hub the station belongs to (only if within the radius, else empty) |

### citibike_hub_summary_YYYY-MM.csv
`hub_id, hub_name, hub_type, radius_m, stations, trips, casual_share, weekday_peak_hour`

### citibike_hub_hourly_YYYY-MM.csv
`hub_id, day_type, hour, trips_total, days, avg_trips` (avg = total / calendar days of that type)

## Findings
_Fill in after running: total trips kept and % removed; which hub has the most bike trips;
which hub has the highest casual share (tourist-heavy?); weekday peak hour; correlation with taxis._

## Limitations
- Citi Bike users are a subset of all travellers; stations sit where the docks are, not where shops are.
- Trips are counted at the START station only (pickups), matching how taxi pickups were counted.
- Hubs far from any dock (e.g. parts of Harlem or the Upper East Side) may have 0 stations in 500 m.
- One month is a small, seasonal sample (January is low season for cycling).
- Check Citi Bike's data licence/attribution terms before redistributing any raw data.
