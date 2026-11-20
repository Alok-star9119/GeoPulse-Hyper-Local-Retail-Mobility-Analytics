# Day 11: Multi-Month Extension

## Why
Every finding so far (Days 6, 9, 10) comes from January 2024 only. One month could be a cold snap, a holiday
or chance. Day 11 runs the same pipeline on more months and checks which patterns **repeat**.

## What was added
| Item | Purpose |
|---|---|
| `src/geopulse/pipeline.py`, `scripts/run_months.py` | Run the six monthly steps (TLC, Citi Bike, panel, quality review, hub rhythm, retail vs mobility) for several months with one command; one failing month does not stop the others; log in `reports/tables/pipeline_run_log.csv`. |
| `src/geopulse/multimonth.py`, `scripts/compare_months.py` | Compare months: overview, rhythm-label stability, hub-rank stability, correlation consistency, weather-effect consistency. |
| `fill_missing_hours` in `ingest_weather.py` | Months with a daylight-saving change (March) have a missing local hour. Gaps of up to 2 h are interpolated and flagged in the new `weather_filled` column; longer gaps stay empty and are reported by the quality check. |
| `tests/test_pipeline.py`, `test_multimonth.py`, `test_weather_fill.py` | Tests on synthetic data with planted structure (hand-made, not real data). |

## How to run
```bash
python scripts/run_months.py --months 2024-02 2024-03 --dry-run   # check the plan first
python scripts/run_months.py --months 2024-02 2024-03
python scripts/compare_months.py
```
Needs the Day 4 (`ingest_osm.py`) and Day 8 (`map_zones_to_hubs.py`) outputs, which do not depend on the month.

## Definitions
- **Label stable**: a hub keeps the same Day 9 rhythm label in every month (months without data are ignored).
- **Rank stable**: Spearman correlation of hub totals between two months (zero totals are treated as no data).
- **Correlation consistent**: the Day 10 Spearman rho has the same sign and |rho| >= 0.3 in every month, with 2+ months.
- **Weather-sensitive**: the mode with the larger % drop in wet or freezing hours.

## Findings
_Fill in after running on real data. Read `reports/day11_multi_month_comparison.md` and write: which patterns repeated, which did not, and one reason for each exception (holiday, weather, coverage)._

## Limitations
- Only winter / early spring months; summer cycling and tourism are not covered.
- With 10 hubs, a rank correlation changes a lot from a single hub moving.
- Repeating in 2-3 months is more credible than one month, but it is not proof.
