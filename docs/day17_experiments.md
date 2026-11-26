# Day 17: Experiments

## Why
Two assumptions made earlier were never tested: that the hand-written rhythm rules of Day 9 describe real
structure in the data, and that weather acts the same way at every time of day (Day 13 used one rain
coefficient). Day 17 tests both on the same tables.

## Experiment A - clusters vs rule labels
- Each hub is described by its normalised hourly profile (24 weekday + 24 weekend shares).
- k-means (k = 2, 3, 4; k-means++ starts) groups the hubs; the best k is chosen by silhouette.
- The grouping is compared with the Day 9 rule labels by **adjusted Rand index** (1 = same grouping, about 0 = chance), and with itself under different random starts (stability).
- Hubs with no data are left out; fewer than 4 hubs means the experiment is skipped and says why.

## Experiment B - rain by time of day
- Rain effect per daypart (night, morning, midday, evening, late) with the Day 6 method (same hour and day type).
- Forecast ablation on the last 7 days: `hour_of_week` vs `additive_weather` vs `rain_by_daypart` (a separate rain coefficient per daypart). If the interaction model is not clearly better, the simpler model stays.
- `forecast.fit_weather_model` gained an optional `design` argument for this; the default behaviour is unchanged (a test checks it).

## How to run
```bash
python scripts/run_experiments.py --year 2024 --month 1
```
Outputs: `reports/tables/experiment_*.csv` and `reports/day17_experiments_YYYY-MM.md`.

## Reading the results
| Result | Meaning |
|---|---|
| ARI near 1, silhouette > 0.5 | The rules match clear groups in the data. |
| ARI near 0, silhouette < 0.25 | Hubs form a continuum; the rhythm labels are a convenient simplification, not real types. |
| Low ARI across seeds | k-means is unstable with so few hubs; do not over-read the clusters. |
| Interaction model WAPE clearly below additive | Rain matters differently at different times of day. |

## Findings
_Fill in after running on real data: the ARI and silhouette for taxi and bike, the daypart where rain hurts most, and whether the interaction model beat the additive one._

## Limitations
- About ten hubs: clustering is suggestive only.
- One month; wet hours per daypart are few, so daypart effects are noisy. Repeat on more months before using these in the report.
- Experiments test the method, they do not establish causes.
