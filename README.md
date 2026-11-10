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
├── data/            # raw -> interim -> processed (not committed, see .gitignore)
├── notebooks/       # exploratory analysis
├── src/geopulse/    # reusable Python package (config, ingestion, cleaning, analysis)
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
python -m geopulse.config        # prints resolved project paths
pytest
```

## Progress
See [docs/progress_log.md](docs/progress_log.md) for the daily log.

## Status
Day 1: project initialised.
