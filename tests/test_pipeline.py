from pathlib import Path

import pytest

from geopulse import pipeline as pl


def test_parse_month():
    assert pl.parse_month("2024-02") == (2024, 2)
    for bad in ("2024-13", "2024-2", "24-02", "feb 2024", "2024-00"):
        with pytest.raises(ValueError):
            pl.parse_month(bad)


def test_plan_order_and_commands(tmp_path):
    plan = pl.build_plan(["2024-02", "2024-03"], tables=tmp_path, scripts=Path("scripts"), python="py")
    assert len(plan) == 12                                          # 6 steps x 2 months
    assert [s.name for s in plan[:6]] == ["ingest_tlc", "ingest_citibike", "build_panel",
                                          "quality_review", "eda_hub_rhythm", "retail_vs_mobility"]
    assert all(s.ym == "2024-02" for s in plan[:6]) and all(s.ym == "2024-03" for s in plan[6:])
    assert plan[0].cmd == ["py", str(Path("scripts") / "ingest_tlc.py"), "--year", "2024", "--month", "2"]
    assert plan[0].output == tmp_path / "tlc_hourly_profile_2024-02.csv"


def test_duplicate_months_are_ignored(tmp_path):
    plan = pl.build_plan(["2024-02", "2024-02"], tables=tmp_path)
    assert len(plan) == 6


def test_skip_existing(tmp_path):
    (tmp_path / "tlc_hourly_profile_2024-02.csv").write_text("x")
    (tmp_path / "citibike_hub_summary_2024-02.csv").write_text("x")
    plan = pl.build_plan(["2024-02"], skip_existing=True, tables=tmp_path)
    assert [s.name for s in plan][0] == "build_panel" and len(plan) == 4
    assert len(pl.build_plan(["2024-02"], skip_existing=False, tables=tmp_path)) == 6


def fake_runner(fail_on=(), codes=None):
    calls = []

    def run(cmd):
        calls.append(cmd)
        script = Path(cmd[1]).name
        month = cmd[5]
        if (script, month) in fail_on:
            return 2, "Traceback: boom"
        return (codes or {}).get(script, 0), "ok"
    run.calls = calls
    return run


def test_run_plan_all_ok(tmp_path):
    plan = pl.build_plan(["2024-02"], tables=tmp_path)
    ticks = iter(range(0, 1000, 3))
    res = pl.run_plan(plan, runner=fake_runner(), clock=lambda: next(ticks))
    assert list(res["status"].unique()) == ["ok"] and (res["seconds"] == 3).all()


def test_failure_stops_that_month_but_not_the_next(tmp_path):
    plan = pl.build_plan(["2024-02", "2024-03"], tables=tmp_path)
    runner = fake_runner(fail_on={("ingest_citibike.py", "2")})
    res = pl.run_plan(plan, runner=runner)
    feb = res[res.month == "2024-02"].set_index("step")["status"]
    mar = res[res.month == "2024-03"]["status"]
    assert feb["ingest_tlc"] == "ok" and feb["ingest_citibike"] == "failed"
    assert (feb[["build_panel", "quality_review", "eda_hub_rhythm", "retail_vs_mobility"]] == "not_run").all()
    assert (mar == "ok").all()
    assert len(runner.calls) == 2 + 6                               # feb stopped after 2 steps; march ran fully
    assert "boom" in res.loc[res.status == "failed", "detail"].iloc[0]


def test_quality_review_exit_code_1_is_not_a_pipeline_failure(tmp_path):
    plan = pl.build_plan(["2024-02"], tables=tmp_path)
    res = pl.run_plan(plan, runner=fake_runner(codes={"quality_review.py": 1})).set_index("step")["status"]
    assert res["quality_review"] == "done_with_fails" and res["eda_hub_rhythm"] == "ok"
    res2 = pl.run_plan(plan, runner=fake_runner(codes={"ingest_tlc.py": 1})).set_index("step")["status"]
    assert res2["ingest_tlc"] == "failed"                           # exit code 1 is only tolerated for quality_review


def test_summarise(tmp_path):
    plan = pl.build_plan(["2024-02", "2024-03"], tables=tmp_path)
    res = pl.run_plan(plan, runner=fake_runner(fail_on={("build_panel.py", "3")}))
    s = pl.summarise(res).set_index("month")
    assert s.loc["2024-02", "ok"] == 6 and s.loc["2024-03", "failed"] == 1 and s.loc["2024-03", "not_run"] == 3
    assert pl.summarise(res.iloc[0:0]).empty


def test_missing_prerequisites(tmp_path):
    miss = pl.missing_prerequisites(tmp_path)
    assert len(miss) == 2 and "ingest_osm.py" in miss[0][1] and "map_zones_to_hubs.py" in miss[1][1]
    (tmp_path / "reports/tables").mkdir(parents=True)
    (tmp_path / "reports/tables/osm_hub_summary.csv").write_text("x")
    (tmp_path / "data/reference").mkdir(parents=True)
    (tmp_path / "data/reference/zone_hub_map.csv").write_text("x")
    assert pl.missing_prerequisites(tmp_path) == []


def test_default_runner_runs_a_real_process(tmp_path):
    code, tail = pl.default_runner(["python3", "-c", "print('hello'); raise SystemExit(3)"], cwd=tmp_path)
    assert code == 3 and "hello" in tail
