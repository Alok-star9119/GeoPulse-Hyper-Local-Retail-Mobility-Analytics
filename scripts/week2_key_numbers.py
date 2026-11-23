"""Day 14: collect headline numbers for the Week 2 summary and the mentor update.

Usage
  python scripts/week2_key_numbers.py

Output (committed): reports/week2_key_numbers.md
"""
import argparse
from pathlib import Path

from geopulse import keynumbers as kn
from geopulse import multimonth as mm
from geopulse.config import PROJECT_ROOT, REPORTS_DIR, ensure_directories


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tables-dir", type=Path, default=REPORTS_DIR / "tables")
    ap.add_argument("--out", type=Path, default=REPORTS_DIR / "week2_key_numbers.md")
    args = ap.parse_args()
    ensure_directories()
    months = mm.discover_months(args.tables_dir, "city_hourly_panel_{ym}.csv")
    text = kn.render(months, kn.quality_summary(args.tables_dir, months), kn.forecast_summary(args.tables_dir, months),
                     kn.stability_summary(args.tables_dir, months), PROJECT_ROOT)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    print(text)
    print(f"Saved: {args.out}")


if __name__ == "__main__":
    main()
