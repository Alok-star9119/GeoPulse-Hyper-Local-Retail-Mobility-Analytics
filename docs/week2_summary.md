# Week 2 Summary - Analysis, Multi-Month Extension and Dashboard

**Project:** GeoPulse - Hyper-Local Retail Mobility Analytics (Manhattan, NYC)
**Period:** Day 8 - Day 14

## What was delivered
| Day | Deliverable | Key files |
|-----|-------------|-----------|
| 8 | Taxi zones mapped to retail hubs; taxi demand added to the hub panel | `src/geopulse/zones.py`, `scripts/map_zones_to_hubs.py` |
| 9 | EDA of daily and weekly rhythm per hub, rule-based rhythm labels | `src/geopulse/eda.py`, `scripts/eda_hub_rhythm.py` |
| 10 | Retail mix vs mobility: trips per 100 POIs, rank correlations with permutation p-values, notebook | `src/geopulse/retail_mobility.py`, `notebooks/` |
| 11 | Multi-month runner and cross-month comparison; DST-safe weather filling | `pipeline.py`, `multimonth.py`, `scripts/run_months.py`, `scripts/compare_months.py` |
| 12 | Offline HTML dashboard (inline SVG) | `dashboard.py`, `scripts/build_dashboard.py` |
| 13 | Baseline hourly demand forecasts with a time-ordered test | `forecast.py`, `scripts/forecast_baseline.py` |
| 14 | Weather-interpolation quality check, key-number summary, this summary | `quality.py` (edited), `keynumbers.py`, `scripts/week2_key_numbers.py` |

## Engineering notes (problems found by tests, then fixed)
- A hub with no station or taxi zone was counted as zero demand in correlations; it is now "no data" (Day 10).
- A daylight-saving gap would have nulled a weather hour and failed the quality check; gaps up to 2 hours are interpolated and flagged (Day 11).
- A rank/correlation table crashed on empty input (Day 12).
- Regressing weather on the residual of a plain hour-of-week mean understated a planted rain effect (-21 instead of -30); levels and weather are now fitted together (Day 13).
- From Day 14 the quality review also reports the share of interpolated weather hours (warn above 1%, fail above 5%).

## How to regenerate the numbers
```bash
python scripts/run_months.py --months 2024-02 2024-03
python scripts/compare_months.py
python scripts/forecast_baseline.py --year 2024 --month 1      # repeat per month
python scripts/build_dashboard.py
python scripts/week2_key_numbers.py                            # writes reports/week2_key_numbers.md
```

## Results
_Fill in from `reports/week2_key_numbers.md` after running on real data: which months were processed, the quality-check outcome per month, forecast WAPE with and without weather, and how many hub labels and correlations were stable across months. Do not copy numbers from anywhere else._

## Known limitations
- Only winter / early-spring months are planned, so seasonal effects are not covered.
- Hub-level hourly counts are small; hub forecasts are noisy.
- All relationships are descriptive and exploratory, not causal.
- Geometry and parquet code was tested on a different machine than it ran on; real-data failures should be reported and fixed.

## Draft mentor update (edit before sending)
> This week I analysed hub-level daily and weekly rhythms, related retail mix to mobility, extended the pipeline to
> several months, built an offline dashboard and added baseline hourly forecasts. [Add 2 real findings from the key-numbers file.]
> Next week: [your plan, e.g. spatial analysis of catchments, deeper weather interaction, final documentation].
