import importlib.util
import json
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
import pytest

matplotlib.use("Agg")
NOTEBOOKS = sorted((Path(__file__).resolve().parents[1] / "notebooks").glob("*.ipynb"))


def code_cells(path):
    nb = json.loads(path.read_text(encoding="utf-8"))
    assert nb["nbformat"] == 4
    return ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.name)
def test_notebook_is_valid_and_compiles(path):
    cells = code_cells(path)
    assert cells, "notebook has no code cells"
    for i, src in enumerate(cells):
        lines = [l for l in src.splitlines() if not l.lstrip().startswith(("%", "!"))]
        compile("\n".join(lines), f"{path.name}[cell {i}]", "exec")


def make_tables(tables: Path):
    """Small synthetic Day 4 / Day 9 tables (hand-made, NOT real data)."""
    rng = np.random.default_rng(0)
    osm, stats = [], []
    for i in range(10):
        fb, fa, sv = int(rng.integers(20, 200)), int(rng.integers(0, 100)), int(rng.integers(2, 20))
        osm.append({"hub_id": f"H{i+1:02d}", "hub_name": f"Hub {i+1}", "hub_type": "mixed", "radius_m": 500,
                    "poi_total": fb + fa + sv, "poi_per_km2": round((fb + fa + sv) / 0.785, 1), "named_share": 0.9,
                    "food_beverage": fb, "fashion": fa, "services": sv})
        for m in ("taxi_pickups", "bike_starts"):
            stats.append({"metric": m, "hub_id": f"H{i+1:02d}", "total": int((fb + fa + sv) * 50 + i),
                          "rush_share": 0.2 + 0.01 * i, "midday_share": 0.2 + 0.005 * i, "evening_share": 0.1,
                          "weekend_ratio": 1.0 + 0.03 * i, "rhythm": "all-day mixed"})
    tables.mkdir(parents=True)
    pd.DataFrame(osm).to_csv(tables / "osm_hub_summary.csv", index=False)
    pd.DataFrame(stats).to_csv(tables / "hub_rhythm_stats_2024-01.csv", index=False)


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.name)
def test_notebook_runs_on_sample_tables(path, tmp_path, monkeypatch):
    (tmp_path / "setup.py").write_text("")
    make_tables(tmp_path / "reports" / "tables")
    monkeypatch.chdir(tmp_path)
    no_ipython = importlib.util.find_spec("IPython") is None      # display() is only needed inside Jupyter
    ns = {"__name__": "__notebook__"}
    for i, src in enumerate(code_cells(path)):
        if no_ipython:
            src = src.replace("from IPython.display import display", "display = lambda *a, **k: None")
        exec(compile(src, f"{path.name}[cell {i}]", "exec"), ns)
    assert "features" in ns and len(ns["features"]) == 10
