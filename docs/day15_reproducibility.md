# Day 15: Repository Hygiene and Reproducibility

## Why
A reviewer should be able to clone the repository, run a few commands and get the same tables.
Earlier in the project, zip files and an assignment PDF nearly got committed by accident; a check that
catches this before every commit is cheap insurance.

## What was added
| Item | Purpose |
|---|---|
| `src/geopulse/hygiene.py`, `scripts/check_repo.py` | Checks that nothing forbidden (zip, parquet, top-level PDF, shapefile parts) or over 5 MB would be committed, every script has a docstring that says how to run it, every docs page is linked from the README, and `.gitignore` has the required rules. Exit code 1 on any problem. Uses `git ls-files`, so ignored files are not reported. |
| `Makefile` | One-word shortcuts: `make test`, `make check`, `make month`, `make months`, `make compare`, `make forecast`, `make dashboard`, `make numbers`. Variables: `YEAR`, `MONTH`, `MONTHS`. |
| `update_docs.py` (helper, run once) | Adds a "Documentation index" to the README for every docs page and the `*.zip` and `/*.pdf` ignore rules. |
| `scripts/plot_study_area.py` | Docstring now says how to run it (found by the new check). |

## Reproduce from scratch
```bash
git clone https://github.com/Alok-star9119/GeoPulse-Hyper-Local-Retail-Mobility-Analytics.git && cd GeoPulse-Hyper-Local-Retail-Mobility-Analytics
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && pip install -e .
make test
python scripts/ingest_osm.py && python scripts/map_zones_to_hubs.py     # static inputs, once
make months MONTHS="2024-01 2024-02 2024-03"
make compare dashboard numbers
make check
```

## Rules the check enforces
- Raw and processed data stay out of git; only small tables and figures are committed.
- Assignment PDFs, zip archives and the final report PDF are not committed here.
- Every script documents its usage in its docstring.

## Limitations
- The check looks at structure, not at whether results are correct; the unit tests and the Day 7 quality review do that.
- `make` is optional; every target is a plain `python scripts/...` command.
