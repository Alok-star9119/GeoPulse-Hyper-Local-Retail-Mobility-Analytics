# Day 9 - Hub Rhythm EDA (daily and weekly patterns)

## Goal
First exploratory analysis step of Week 2: **when is each retail hub busy?** Compare the daily
shape of taxi and bike activity per hub, weekday vs weekend, and spot unusual days.

## Method
1. Use the hub panel (hub x hour) and city panel from Days 6 and 8.
2. **Hourly rhythm:** average volume per hub, day type (weekday/weekend) and hour, plus each hour's
   share of that day type's daily volume. Shares make hubs of different sizes comparable by shape.
3. **Weekly heatmap:** day-of-week x hour averages for Manhattan (city level).
4. **Per-hub statistics:** weekday/weekend peak hour, peak-to-mean ratio (how concentrated the
   volume is), share of volume in rush hours (07-09, 17-19), midday (11-14) and evening (20-23),
   five dayparts, and the **weekend ratio** (average weekend day / average weekday day).
5. **Rhythm label** from transparent rules (thresholds are constants in `src/geopulse/eda.py`):
   commuter, leisure / evening, midday / shopping, all-day mixed, or no data.
6. **Profile similarity:** hub x hub correlation of weekday hourly shapes (input for clustering later).
7. **Busiest / quietest days** with precipitation and temperature, to explain unusual days.

## Run
```bash
source .venv/bin/activate
pytest -q
python scripts/eda_hub_rhythm.py --year 2024 --month 1
```
(`build_panel.py` must have run first; run `map_zones_to_hubs.py` + `build_panel.py` for taxi by hub.)

## Outputs
| File | Committed? |
|------|-----------|
| reports/tables/hub_rhythm_stats_YYYY-MM.csv | Yes |
| reports/tables/hub_hourly_rhythm_YYYY-MM.csv | Yes |
| reports/tables/city_weekly_heatmap_YYYY-MM.csv | Yes |
| reports/tables/hub_profile_similarity_YYYY-MM.csv | Yes |
| reports/tables/daily_extremes_YYYY-MM.csv | Yes |
| reports/day9_hub_rhythm_YYYY-MM.md (auto-generated report) | Yes |
| reports/figures/hub_rhythm_taxi_pickups_YYYY-MM.png, hub_rhythm_bike_starts_YYYY-MM.png | Yes |
| reports/figures/hub_dayparts_<metric>_YYYY-MM.png | Yes |
| reports/figures/weekly_heatmap_YYYY-MM.png | Yes |

## Data dictionary: hub_rhythm_stats
| Column | Description |
|--------|-------------|
| metric | taxi_pickups or bike_starts |
| hub_id, hub_name, hub_type | Hub |
| total | Volume in the month in the hub catchment |
| weekday_peak_hour / weekend_peak_hour | Hour with the highest average volume |
| peak_to_mean | Peak hour / average hour on weekdays (1 = perfectly flat) |
| rush_share, midday_share, evening_share | Share of weekday volume in those hours |
| weekend_ratio | Avg weekend-day volume / avg weekday-day volume |
| share_night, share_morning, share_midday, share_afternoon, share_evening | Weekday dayparts (sum to 1) |
| rhythm | Rule-based label |

## Findings
_Fill in after running (use `reports/day9_hub_rhythm_YYYY-MM.md`): which hubs are commuter vs
leisure; which hub has the strongest weekend uplift; whether taxi and bike peaks agree; the
busiest and quietest days and their weather._

## Limitations
- Descriptive, one month (January 2024): patterns are indicative and seasonal.
- Labels depend on thresholds that were chosen, not learned; check the numbers behind each label.
- Bike counts only cover docks within the hub radius; taxi counts cover whole assigned zones.
- Hubs with no Citi Bike stations show "no data" for bikes (a coverage gap, not zero demand).
- Perfectly flat profiles have undefined correlations (NaN) in the similarity table.
