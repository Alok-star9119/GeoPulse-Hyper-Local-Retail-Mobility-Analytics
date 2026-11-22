# Day 13: Baseline Demand Forecasts

## Why
Days 9-11 describe *when* hubs are busy and which patterns repeat. A forecast baseline asks a sharper
question: how predictable is hourly demand, and does weather add anything beyond the weekly pattern?
Baselines also set the bar any later, fancier model must beat.

## Models (all numpy, no extra packages)
| Model | Idea |
|---|---|
| `seasonal_naive` | Same weekday and hour one week earlier. |
| `hour_of_week` | Mean of the training weeks for that weekday and hour (168 levels). |
| `hour_of_week_weather` | The 168 levels fitted together with a linear effect of a wet hour, snow and temperature (backfitting). |

A first version regressed the residual of the plain hour-of-week mean on weather; the test showed it
understated a planted rain effect (-21 instead of -30), because the mean already contains the rain of
past weeks. Fitting levels and weather together fixes that.

## Evaluation
Time-ordered split: the last 7 days of the month are the test set, nothing is shuffled. Metrics: MAE,
WAPE (total absolute error / total actual) and bias. Zero-demand series are reported as no data, and
percentage error is left empty when actual demand is 0.

## How to run
```bash
python scripts/forecast_baseline.py --year 2024 --month 1
```
Outputs: `reports/tables/forecast_metrics_YYYY-MM.csv`, `forecast_hub_metrics_YYYY-MM.csv`,
`reports/figures/forecast_city_YYYY-MM.png`, `reports/day13_forecast_baselines_YYYY-MM.md`.

## Findings
_Fill in after running on real data: city-level WAPE of each model, whether weather lowers WAPE and by how many points, and which hubs are hardest to forecast._

## Limitations
- One month = about 3 training weeks; holidays in the test week are not predictable.
- Linear weather effect; no interaction with hour of day (rain may matter more at rush hour).
- Hub counts per hour are small, so hub WAPE is much higher than city WAPE.
- Not a production forecast: no trend, no holiday calendar, no multi-month training.
