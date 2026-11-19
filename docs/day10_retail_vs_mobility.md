# Day 10 - Retail Mix vs Mobility (first notebook)

## Goal
Connect two things built earlier: **what kind of shops surround a hub** (Day 4, OpenStreetMap) and
**how people move there** (taxi and bike volume and rhythm, Days 8-9). The aim is to ask which
retail characteristics go together with busier or differently-shaped hubs, and to find hubs with a
lot of movement relative to their retail supply.

## Method
1. **Retail features** per hub: category shares (% of the hub's POIs), POI density per km2, dominant
   category, and a **diversity** score (normalised Shannon entropy: 0 = one category, 1 = evenly mixed).
2. **Mobility features** per hub from `hub_rhythm_stats`: total volume, rush / midday / evening share,
   weekend ratio, for taxi and bike. A total of 0 means "no data" (no bike station, no taxi zone) and is
   left out, not treated as "no demand".
3. **Trips per 100 POIs**: mobility relative to retail supply (rough index).
4. **Rank correlations** (Spearman) between every retail feature and mobility feature, with the number
   of hubs used and a permutation p-value.
5. **Rhythm groups**: average retail profile of hubs with the same rhythm label (commuter, leisure ...).

## Why the statistics are cautious
There are only about ten hubs, one month of data, and dozens of pairs are tested. Roughly one in
twenty pairs reaches p < 0.05 by pure chance. The report prints this expected number. Treat results
as questions for the next months of data, not as proof, and look for patterns that agree between taxi
and bike.

## Run
```bash
source .venv/bin/activate
pytest -q
python scripts/retail_vs_mobility.py --year 2024 --month 1
jupyter lab notebooks/01_retail_mix_vs_mobility.ipynb      # or open it in VS Code
```
Inputs needed: `reports/tables/osm_hub_summary.csv` (Day 4) and `reports/tables/hub_rhythm_stats_YYYY-MM.csv` (Day 9).

**Notebook:** in VS Code choose the `.venv` kernel, run **Restart and Run All**, write your findings
in the last cell, then save. Saved outputs (charts) show up when the notebook is opened on GitHub.

## Outputs
| File | Committed? |
|------|-----------|
| reports/tables/hub_feature_table_YYYY-MM.csv | Yes |
| reports/tables/retail_mobility_correlations_YYYY-MM.csv | Yes |
| reports/tables/rhythm_group_summary_YYYY-MM.csv | Yes |
| reports/day10_retail_vs_mobility_YYYY-MM.md | Yes |
| reports/figures/retail_mix_heatmap_YYYY-MM.png | Yes |
| reports/figures/poi_density_vs_trips_YYYY-MM.png | Yes |
| reports/figures/trips_per_poi_YYYY-MM.png | Yes |
| notebooks/01_retail_mix_vs_mobility.ipynb | Yes |

## Data dictionary: hub_feature_table
| Column | Description |
|--------|-------------|
| hub_id, hub_name, hub_type | Hub |
| poi_total, poi_per_km2 | POIs within the hub radius and density |
| share_<category> | Share of the hub's POIs in that category |
| diversity | Normalised entropy of the category mix (0-1) |
| dominant_category, dominant_share | Most common category and its share |
| taxi_* / bike_* | total, rush_share, midday_share, evening_share, weekend_ratio, rhythm from Day 9 |
| taxi_per_100_poi / bike_per_100_poi | Monthly trips per 100 POIs (empty when no data) |

## Findings
_Fill in from `reports/day10_retail_vs_mobility_YYYY-MM.md` and the notebook: which hubs are the
densest and most diverse; whether density goes with volume for both taxi and bike; the hub with the
highest trips per 100 POIs and a possible reason._

## Limitations
- About ten hubs and one month: correlations are unstable and exploratory.
- OpenStreetMap completeness differs between neighbourhoods; low POI counts may be missing data.
- Taxi counts cover whole zones and bike counts only nearby docks, so volumes are not like-for-like.
- Correlation is not cause: busy places may attract shops as much as shops attract trips.
