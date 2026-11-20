"""Day 11: run the monthly pipeline for several months with one command.

Usage
  python scripts/run_months.py --months 2024-02 2024-03            # run both months
  python scripts/run_months.py --months 2024-02 2024-03 --dry-run  # only show what would run
  python scripts/run_months.py --months 2024-02 --skip-existing    # skip steps whose output exists

Steps per month: ingest_tlc, ingest_citibike, build_panel, quality_review, eda_hub_rhythm,
retail_vs_mobility. Needs internet (downloads) and the two static inputs from Days 4 and 8.
If a step fails, the remaining steps of that month are skipped and the next month still runs.

Output (committed): reports/tables/pipeline_run_log.csv
"""
import argparse
from datetime import datetime

from geopulse.config import PROJECT_ROOT, REPORTS_DIR, ensure_directories
from geopulse.pipeline import (build_plan, missing_prerequisites, parse_month, run_plan,
                               summarise)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", nargs="+", required=True, help="e.g. 2024-02 2024-03")
    ap.add_argument("--skip-existing", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    try:
        for ym in args.months:
            parse_month(ym)
    except ValueError as err:
        raise SystemExit(str(err))

    missing = missing_prerequisites()
    if missing:
        lines = "\n".join(f"  - {p} is missing. Run: {how}" for p, how in missing)
        raise SystemExit(f"Static inputs needed before the monthly steps:\n{lines}")

    plan = build_plan(args.months, args.skip_existing)
    print(f"{len(plan)} steps for {len(set(s.ym for s in plan))} month(s)")
    for st in plan:
        print(f"  {st.ym}  {st.name:20s} {' '.join(st.cmd[1:])}")
    if args.dry_run or not plan:
        print("(dry run, nothing executed)" if args.dry_run else "Nothing to do: all outputs exist.")
        return

    ensure_directories()
    results = run_plan(plan)
    results.insert(0, "run_at", datetime.now().strftime("%Y-%m-%d %H:%M"))
    log = REPORTS_DIR / "tables" / "pipeline_run_log.csv"
    results.to_csv(log, index=False)
    print("\n" + summarise(results).to_string(index=False))
    bad = results[results["status"].isin(["failed", "not_run"])]
    if len(bad):
        print("\nProblems:")
        print(bad[["month", "step", "status", "detail"]].to_string(index=False))
    print(f"\nLog: {log.relative_to(PROJECT_ROOT)}")
    print("Next: python scripts/compare_months.py")
    raise SystemExit(1 if (results["status"] == "failed").any() else 0)


if __name__ == "__main__":
    main()
