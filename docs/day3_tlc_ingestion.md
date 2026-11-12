# Day 3 - NYC TLC Taxi Ingestion

## Goal
Bring real mobility data into the project and turn it into a first usable table:
average taxi pickups per hour for each Manhattan zone.

## Steps
1. Download one month of yellow-taxi trips and the taxi-zone lookup (`geopulse.download`).
2. Read only 7 needed columns from the Parquet file.
3. Validate: count nulls, out-of-month rows, negative durations, bad distances, duplicates.
4. Clean with fixed rules (see `docs/data_dictionary.md`).
5. Keep trips whose pickup zone is in Manhattan.
6. Aggregate to average pickups by zone x day type (weekday/weekend) x hour.

## Run
```bash
pip install -r requirements.txt && pip install -e .
python scripts/ingest_tlc.py --year 2024 --month 1
```

## Outputs
| File | Committed? |
|------|-----------|
| data/raw/tlc/* | No (large, git-ignored) |
| data/interim/tlc_manhattan_YYYY-MM.parquet | No |
| reports/tables/tlc_quality_YYYY-MM.json | Yes |
| reports/tables/tlc_hourly_profile_YYYY-MM.csv | Yes |
| reports/figures/tlc_hourly_profile_YYYY-MM.png | Yes |
| data/reference/data_sources_catalog.csv (status/last_verified updated) | Yes |

## Findings
_Fill in after running: total rows, % removed by cleaning, peak hour on weekdays vs weekends._

## Limitations
- Taxi zones are polygons, not points, so hub-level analysis (Day 4+) will map zones to hubs.
- Yellow taxis are only a sample of all movement (no green taxi, for-hire vehicles or bikes yet).
- Tips paid in cash are not in `total_amount`.
