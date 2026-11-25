# Day 16: Findings Draft and Project Wrap-Up

## Why
Fifteen days of code produced many tables. The final report needs correct numbers, and numbers typed by hand
can drift from the data. Day 16 generates a findings draft straight from the committed tables, so every figure
can be traced to a file.

## What was added
| Item | Purpose |
|---|---|
| `src/geopulse/findings.py`, `scripts/build_findings.py` | Writes `reports/final_findings_draft.md`: coverage, hub profiles (busiest/quietest hub, rhythm labels, no-data hubs), retail-mobility correlations (only "repeats in every month" claims when 2+ months exist), weather effects, forecast accuracy, data quality and limitations. |
| `src/geopulse/catalog.py` | Writes `docs/table_catalog.md`: every result table, number of monthly files, rows and columns. |
| `Makefile` | New `make findings` target (existing file extended). |
| `tests/test_findings.py` | Checks the text against planted structure in synthetic tables, the one-month and empty cases. |

## How to run
```bash
python scripts/run_months.py --months 2024-02 2024-03     # if not done yet
python scripts/compare_months.py
python scripts/forecast_baseline.py --year 2024 --month 1  # repeat per month
python scripts/build_dashboard.py
python scripts/build_findings.py
python scripts/check_repo.py
```

## How to use the draft
1. Read `reports/final_findings_draft.md` next to `reports/dashboard.html`.
2. Check two or three numbers against the source tables.
3. Rewrite in your own words and add interpretation (why a hub is commuter-like, what a weather effect means for retail).
4. Fill the "Findings" sections of the Day 9-13 docs from the same numbers.

## Wording rules the generator follows
- Descriptive only; correlations are "associations", with a reminder about ten hubs and many tested pairs.
- A hub with no coverage is "no data", never zero demand.
- With one month, no "repeats across months" claim is made.

## Limitations
- The draft states facts; it does not explain them. Interpretation is the author's job.
- It reads whatever months exist; months with failed quality checks are listed so they can be excluded.
