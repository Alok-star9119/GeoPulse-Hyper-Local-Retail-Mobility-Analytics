"""Day 16: generate the findings draft and the table catalog from the result tables.

Usage
  python scripts/build_findings.py

Outputs (committed): reports/final_findings_draft.md and docs/table_catalog.md
Run after run_months.py, compare_months.py and forecast_baseline.py so all tables exist.
"""
import argparse
from pathlib import Path

from geopulse import catalog, findings
from geopulse import multimonth as mm
from geopulse.config import PROJECT_ROOT, REPORTS_DIR, ensure_directories


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tables-dir", type=Path, default=REPORTS_DIR / "tables")
    ap.add_argument("--out", type=Path, default=REPORTS_DIR / "final_findings_draft.md")
    ap.add_argument("--catalog-out", type=Path, default=PROJECT_ROOT / "docs" / "table_catalog.md")
    args = ap.parse_args()
    ensure_directories()
    months = mm.discover_months(args.tables_dir, "city_hourly_panel_{ym}.csv")
    for path, text in ((args.out, findings.build(args.tables_dir, months)),
                       (args.catalog_out, catalog.render(catalog.build_catalog(args.tables_dir)))):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print(f"Wrote {path}")
    print(f"Months: {', '.join(months) or 'none'}. Now read the draft and compare it with reports/dashboard.html.")


if __name__ == "__main__":
    main()
