"""Day 12: build a single-file HTML dashboard from the report tables.

Usage
  python scripts/build_dashboard.py                      # every processed month
  python scripts/build_dashboard.py --months 2024-01 2024-02

Output (committed): reports/dashboard.html  (open it in a browser; works offline)
"""
import argparse
from pathlib import Path

from geopulse import multimonth as mm
from geopulse.config import REPORTS_DIR, ensure_directories
from geopulse.dashboard import render


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", nargs="+")
    ap.add_argument("--tables-dir", type=Path, default=REPORTS_DIR / "tables")
    ap.add_argument("--out", type=Path, default=REPORTS_DIR / "dashboard.html")
    args = ap.parse_args()
    ensure_directories()
    months = sorted(set(args.months)) if args.months else mm.discover_months(args.tables_dir, "city_hourly_panel_{ym}.csv")
    if not months:
        raise SystemExit("No processed months found. Run: python scripts/build_panel.py --year 2024 --month 1")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(months, args.tables_dir), encoding="utf-8")
    print(f"Dashboard for {len(months)} month(s): {args.out}")


if __name__ == "__main__":
    main()
