"""Day 11: run the per-month pipeline (Days 3, 5, 6, 7, 9, 10) for several months in one go.

Each step is an existing script run as a separate process, so nothing is re-implemented and every
step keeps working on its own. Static inputs (OpenStreetMap POIs from Day 4 and the zone -> hub map
from Day 8) do not depend on the month; they must exist before the monthly steps run.
"""
from __future__ import annotations

import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pandas as pd

from geopulse.config import PROJECT_ROOT

TABLES = PROJECT_ROOT / "reports" / "tables"
SCRIPTS = PROJECT_ROOT / "scripts"

# (step name, script, takes --year/--month, expected output for skip-existing, exit codes that still count as done)
STEPS = [
    ("ingest_tlc", "ingest_tlc.py", "tlc_hourly_profile_{ym}.csv", (0,)),
    ("ingest_citibike", "ingest_citibike.py", "citibike_hub_summary_{ym}.csv", (0,)),
    ("build_panel", "build_panel.py", "hub_hourly_panel_{ym}.csv", (0,)),
    ("quality_review", "quality_review.py", "quality_checks_{ym}.csv", (0, 1)),   # 1 = a check failed; outputs still written
    ("eda_hub_rhythm", "eda_hub_rhythm.py", "hub_rhythm_stats_{ym}.csv", (0,)),
    ("retail_vs_mobility", "retail_vs_mobility.py", "hub_feature_table_{ym}.csv", (0,)),
]

PREREQUISITES = [
    (Path("reports/tables/osm_hub_summary.csv"), "python scripts/ingest_osm.py"),
    (Path("data/reference/zone_hub_map.csv"), "python scripts/map_zones_to_hubs.py"),
]


@dataclass
class Step:
    name: str
    ym: str
    cmd: list
    output: Path
    ok_codes: tuple


def parse_month(text: str) -> tuple[int, int]:
    """'2024-02' -> (2024, 2). Raises ValueError for anything else."""
    m = re.fullmatch(r"(\d{4})-(\d{2})", text.strip())
    if not m or not 1 <= int(m.group(2)) <= 12:
        raise ValueError(f"Month must look like 2024-02, got {text!r}")
    return int(m.group(1)), int(m.group(2))


def missing_prerequisites(root: Path = PROJECT_ROOT) -> list[tuple[Path, str]]:
    return [(p, how) for p, how in PREREQUISITES if not (root / p).exists()]


def build_plan(months: list[str], skip_existing: bool = False, tables: Path = TABLES,
               scripts: Path = SCRIPTS, python: str = sys.executable) -> list[Step]:
    """One Step per month and script, in pipeline order. Months are de-duplicated, order kept."""
    plan, seen = [], set()
    for ym in months:
        if ym in seen:
            continue
        seen.add(ym)
        y, m = parse_month(ym)
        for name, script, out, ok in STEPS:
            output = tables / out.format(ym=ym)
            if skip_existing and output.exists():
                continue
            cmd = [python, str(scripts / script), "--year", str(y), "--month", str(m)]
            plan.append(Step(name, ym, cmd, output, ok))
    return plan


def default_runner(cmd: list, cwd: Path = PROJECT_ROOT) -> tuple[int, str]:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    tail = (proc.stdout + proc.stderr).strip().splitlines()[-3:]
    return proc.returncode, " | ".join(tail)


def run_plan(plan: list[Step], runner: Callable[[list], tuple[int, str]] = default_runner,
             clock: Callable[[], float] = time.monotonic) -> pd.DataFrame:
    """Run steps in order. If a step fails, the rest of that month is skipped; other months continue."""
    rows, failed_months = [], set()
    for st in plan:
        if st.ym in failed_months:
            rows.append({"month": st.ym, "step": st.name, "status": "not_run", "seconds": 0.0,
                         "detail": "an earlier step for this month failed"})
            continue
        t0 = clock()
        code, tail = runner(st.cmd)
        secs = round(clock() - t0, 1)
        if code in st.ok_codes:
            status = "ok" if code == 0 else "done_with_fails"
        else:
            status = "failed"
            failed_months.add(st.ym)
        rows.append({"month": st.ym, "step": st.name, "status": status, "seconds": secs,
                     "detail": "" if status == "ok" else tail})
    return pd.DataFrame(rows, columns=["month", "step", "status", "seconds", "detail"])


def summarise(results: pd.DataFrame) -> pd.DataFrame:
    """One row per month: how many steps ok / failed / not run."""
    if results.empty:
        return pd.DataFrame(columns=["month", "ok", "done_with_fails", "failed", "not_run"])
    t = results.pivot_table(index="month", columns="status", values="step", aggfunc="count", fill_value=0)
    for c in ("ok", "done_with_fails", "failed", "not_run"):
        if c not in t.columns:
            t[c] = 0
    return t[["ok", "done_with_fails", "failed", "not_run"]].reset_index()
