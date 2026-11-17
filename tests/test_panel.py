import http.server
import json
import threading

import numpy as np
import pandas as pd
import pytest

from geopulse import ingest_weather as w
from geopulse import panel as p
from geopulse.download import download_file
from geopulse.sources import get_hubs

# ---------- weather ----------
def fake_weather_json(year=2024, month=1, n=None):
    times = pd.date_range(f"{year}-{month:02d}-01", periods=n or 31 * 24, freq="h")
    return {"hourly": {
        "time": [t.strftime("%Y-%m-%dT%H:%M") for t in times],
        "temperature_2m": [-2.0 if t.hour < 6 else 3.0 for t in times],
        "precipitation": [0.5 if t.day == 5 else 0.0 for t in times],
        "rain": [0.0] * len(times), "snowfall": [0.0] * len(times),
        "wind_speed_10m": [10.0] * len(times), "weather_code": [3] * len(times)}}


def test_build_url():
    u = w.build_url(2024, 2)
    assert "start_date=2024-02-01" in u and "end_date=2024-02-29" in u   # leap year
    assert "timezone=America%2FNew_York" in u and "precipitation" in u


def test_parse_and_flags():
    df = w.add_weather_flags(w.parse_hourly(fake_weather_json()))
    assert len(df) == 744 and "temp_c" in df.columns
    assert df.is_wet.sum() == 24                  # all of day 5
    assert df.is_cold.sum() == 31 * 6             # hours 0-5 are -2 C
    q = w.weather_quality(df, 2024, 1)
    assert q["rows"] == q["expected_rows"] == 744 and q["wet_hours"] == 24


def test_parse_rejects_bad_response():
    with pytest.raises(ValueError):
        w.parse_hourly({"error": True, "reason": "bad"})
    bad = fake_weather_json()
    del bad["hourly"]["rain"]
    with pytest.raises(ValueError):
        w.parse_hourly(bad)


def test_download_weather_from_local_server(tmp_path, monkeypatch):
    body = json.dumps(fake_weather_json()).encode()

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200); self.send_header("Content-Length", str(len(body)))
            self.end_headers(); self.wfile.write(body)
        def log_message(self, *a): pass
    httpd = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        monkeypatch.setattr(w, "WEATHER_RAW_DIR", tmp_path)
        path = w.download_weather(2024, 1, base=f"http://127.0.0.1:{httpd.server_port}/v1/archive")
        assert len(w.load_weather(path)) == 744
    finally:
        httpd.shutdown()


# ---------- panel ----------
@pytest.fixture
def weather():
    return w.add_weather_flags(w.parse_hourly(fake_weather_json()))


@pytest.fixture
def stations():
    return pd.DataFrame({"station_id": ["A", "B", "C"], "hub_id": ["H01", "H01", "H02"]})


@pytest.fixture
def agg():
    rows = [("A", "2024-01-02", 8, 3), ("B", "2024-01-02", 8, 2), ("C", "2024-01-02", 9, 4),
            ("Z", "2024-01-02", 8, 99)]                  # Z has no hub -> ignored
    return pd.DataFrame([{"start_station_id": s, "start_station_name": s, "date": d, "hour": h,
                          "user_type": "member", "trips": t, "lat_sum": 0.0, "lng_sum": 0.0}
                         for s, d, h, t in rows])


def test_taxi_hourly():
    trips = pd.DataFrame({"tpep_pickup_datetime": pd.to_datetime(
        ["2024-01-02 08:10", "2024-01-02 08:50", "2024-01-02 09:00"])})
    t = p.taxi_hourly(trips).set_index("datetime")["taxi_pickups"]
    assert t[pd.Timestamp("2024-01-02 08:00")] == 2 and t[pd.Timestamp("2024-01-02 09:00")] == 1


def test_bike_hourly_by_hub(agg, stations):
    b = p.bike_hourly_by_hub(agg, stations).set_index(["hub_id", "datetime"])["bike_starts"]
    assert b[("H01", pd.Timestamp("2024-01-02 08:00"))] == 5
    assert b[("H02", pd.Timestamp("2024-01-02 09:00"))] == 4
    assert b.sum() == 9


def test_city_panel_shape_and_fill(agg, stations, weather):
    taxi = pd.DataFrame({"datetime": [pd.Timestamp("2024-01-02 08:00")], "taxi_pickups": [7]})
    c = p.city_panel(taxi, p.bike_hourly_by_hub(agg, stations), weather, 2024, 1)
    assert len(c) == 744 and c["datetime"].is_unique
    assert c.taxi_pickups.sum() == 7 and c.bike_starts_hubs.sum() == 9
    assert c.temp_c.notna().all()
    assert set(c.day_type) == {"weekday", "weekend"}


def test_hub_panel_full_grid_and_osm(agg, stations, weather):
    hubs = get_hubs()
    osm = pd.DataFrame({"hub_id": ["H01"], "hub_name": ["x"], "hub_type": ["y"], "radius_m": [500],
                        "poi_total": [42], "poi_per_km2": [53.5], "named_share": [0.9], "fashion": [5]})
    h = p.hub_panel(p.bike_hourly_by_hub(agg, stations), weather, hubs, 2024, 1, osm)
    assert len(h) == 10 * 744
    assert h.bike_starts.sum() == 9
    assert h.loc[h.hub_id == "H01", "osm_poi_total"].eq(42).all()
    assert h.loc[h.hub_id == "H02", "osm_poi_total"].isna().all()
    assert "hub_name" in h.columns and h["hub_name"].notna().all()


def test_weather_effect_recovers_known_drop():
    # Build a panel where wet hours have exactly half the bike trips of dry hours at the same hour
    hours = pd.date_range("2024-01-01", periods=14 * 24, freq="h")
    df = pd.DataFrame({"datetime": hours})
    df["hour"] = df.datetime.dt.hour
    df["day_type"] = np.where(df.datetime.dt.dayofweek >= 5, "weekend", "weekday")
    df["is_wet"] = df.datetime.dt.day % 3 == 0
    base = 10 + df["hour"]
    df["bike"] = np.where(df.is_wet, base * 0.5, base)
    df["taxi"] = base                                     # no weather effect
    out = p.weather_effect(df, ["bike", "taxi"], "is_wet").set_index("metric")
    assert out.loc["bike", "change_pct"] == pytest.approx(-50.0, abs=0.1)
    assert out.loc["taxi", "change_pct"] == pytest.approx(0.0, abs=0.1)


def test_weather_effect_without_wet_hours_gives_nan():
    df = pd.DataFrame({"hour": [1, 2], "day_type": ["weekday"] * 2, "is_wet": [False, False], "bike": [1, 2]})
    out = p.weather_effect(df, ["bike"], "is_wet")
    assert np.isnan(out.change_pct.iloc[0])


def test_daily_summary(agg, stations, weather):
    taxi = pd.DataFrame({"datetime": [pd.Timestamp("2024-01-02 08:00")], "taxi_pickups": [7]})
    c = p.city_panel(taxi, p.bike_hourly_by_hub(agg, stations), weather, 2024, 1)
    d = p.daily_summary(c)
    assert len(d) == 31 and d.taxi_pickups.sum() == 7
    assert d.loc[d.date == pd.Timestamp("2024-01-05").date(), "precip_mm"].iloc[0] == 12.0


# ---------- Day 8: taxi by hub, mode summary ----------
def _zone_map():
    return pd.DataFrame({"LocationID": [10, 11, 12], "hub_id": ["H01", "H01", None]})


def test_taxi_hourly_by_hub_uses_zone_map():
    trips = pd.DataFrame({
        "tpep_pickup_datetime": pd.to_datetime(["2024-01-02 08:10", "2024-01-02 08:50",
                                                "2024-01-02 09:00", "2024-01-02 08:20"]),
        "PULocationID": [10, 11, 10, 12]})            # zone 12 has no hub -> ignored
    t = p.taxi_hourly_by_hub(trips, _zone_map()).set_index(["hub_id", "datetime"])["taxi_pickups"]
    assert t[("H01", pd.Timestamp("2024-01-02 08:00"))] == 2
    assert t[("H01", pd.Timestamp("2024-01-02 09:00"))] == 1
    assert t.sum() == 3


def test_hub_panel_with_taxi_and_mode_summary(agg, stations, weather):
    hubs = get_hubs()
    bike = p.bike_hourly_by_hub(agg, stations)
    taxi = pd.DataFrame({"hub_id": ["H01", "H01", "H02"],
                         "datetime": pd.to_datetime(["2024-01-02 08:00", "2024-01-02 09:00", "2024-01-02 09:00"]),
                         "taxi_pickups": [6, 4, 10]})
    h = p.hub_panel(bike, weather, hubs, 2024, 1, taxi_hub_h=taxi)
    assert len(h) == 7440 and h.taxi_pickups.sum() == 20
    assert "taxi_pickups" not in p.hub_panel(bike, weather, hubs, 2024, 1).columns   # still optional
    s = p.hub_mode_summary(h).set_index("hub_id")
    assert s.loc["H01", "taxi_pickups"] == 10 and s.loc["H01", "bike_starts"] == 5
    assert s.loc["H01", "taxi_share"] == pytest.approx(10 / 15, abs=0.001)
    assert s.loc["H01", "weekday_peak_hour_taxi"] == 8
    assert s.loc["H10", "taxi_pickups"] == 0 and np.isnan(s.loc["H10", "taxi_share"])
    with pytest.raises(ValueError):
        p.hub_mode_summary(p.hub_panel(bike, weather, hubs, 2024, 1))
