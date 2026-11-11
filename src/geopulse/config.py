"""Central project configuration: paths and constants."""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"
REFERENCE_DIR = DATA_DIR / "reference"  # small, committed lookup files

REPORTS_DIR = PROJECT_ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"
DASHBOARD_DIR = PROJECT_ROOT / "dashboards"

RANDOM_SEED = 42


def ensure_directories() -> None:
    """Create all data/report directories if they do not exist."""
    for path in (RAW_DIR, INTERIM_DIR, PROCESSED_DIR, FIGURES_DIR, DASHBOARD_DIR):
        path.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    ensure_directories()
    print(f"Project root : {PROJECT_ROOT}")
    print(f"Raw data     : {RAW_DIR}")
    print(f"Interim data : {INTERIM_DIR}")
    print(f"Processed    : {PROCESSED_DIR}")
    print(f"Figures      : {FIGURES_DIR}")
