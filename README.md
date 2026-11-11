# GeoPulse: Hyper-Local Retail Mobility Analytics

GeoPulse analyses foot-traffic and mobility patterns around retail locations to
uncover trends, peak hours, catchment areas and actionable business insights,
delivered through interactive dashboards and reports.

## Project Objectives
- Collect, clean and validate mobility / retail datasets from multiple sources
- Perform exploratory and geospatial analysis
- Build interactive dashboards and analytical reports
- Document every step following industry standards

## Project Structure
```
geopulse/
├── data/            # raw/interim/processed (not committed); reference/ (committed)
├── notebooks/       # exploratory analysis
├── src/geopulse/    # reusable Python package (config, ingestion, cleaning, analysis)
├── scripts/         # runnable utilities
├── sql/             # SQL queries
├── dashboards/      # dashboard files / app
├── reports/         # final reports and figures
├── docs/            # project plan, data dictionary, progress log
└── tests/           # unit tests
```

## Getting Started
```bash
git clone <your-repo-url> && cd geopulse
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .                 # makes the geopulse package importable
python -m geopulse.config        # prints resolved project paths
pytest
python scripts/plot_study_area.py   # regenerates reports/figures/study_area_hubs.png
python scripts/check_sources.py     # checks source links (needs internet)
```

## Progress
See [docs/progress_log.md](docs/progress_log.md) for the daily log.

## Status
- Day 1: project initialised.
- Day 2: data sources researched and catalogued, study area defined (Manhattan).
  See [docs/data_sources.md](docs/data_sources.md) and `data/reference/`.
