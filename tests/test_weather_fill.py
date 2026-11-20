import numpy as np
import pandas as pd
import pytest

from geopulse import ingest_weather as w
from geopulse import panel as p
from geopulse import quality as q


def raw_weather(year, month, drop=(), duplicate=()):
    """Hourly weather JSON for a month, with chosen (day, hour) rows removed or repeated."""
    times = list(pd.date_range(f"{year}-{month:02d}-01", periods=pd.Period(f"{year}-{month:02d}").days_in_month * 24, freq="h"))
    times = [t for t in times if (t.day, t.hour) not in drop]
    for dh in duplicate:
        i = next(k for k, t in enumerate(times) if (t.day, t.hour) == dh)
        times.insert(i, times[i])
    n = len(times)
    return {"hourly": {"time": [t.strftime("%Y-%m-%dT%H:%M") for t in times],
                       "temperature_2m": [float(t.hour) for t in times], "precipitation": [0.0] * n,
                       "rain": [0.0] * n, "snowfall": [0.0] * n, "wind_speed_10m": [9.0] * n,
                       "weather_code": [3] * n}}


def test_complete_month_is_unchanged():
    d = w.fill_missing_hours(w.parse_hourly(raw_weather(2024, 1)), 2024, 1)
    assert len(d) == 744 and not d["weather_filled"].any()
    assert d["temp_c"].notna().all()


def test_dst_spring_forward_gap_is_filled_and_marked():
    raw = w.parse_hourly(raw_weather(2024, 3, drop={(10, 2)}))        # API skips the 02:00 that does not exist
    assert len(raw) == 743
    d = w.fill_missing_hours(raw, 2024, 3)
    assert len(d) == 744 and d["weather_filled"].sum() == 1
    row = d[d.datetime == pd.Timestamp("2024-03-10 02:00")].iloc[0]
    assert row["weather_filled"] and row["temp_c"] == pytest.approx(2.0)      # between 01:00 (1 C) and 03:00 (3 C)
    assert row["weather_code"] == 3


def test_dst_fall_back_duplicate_hour_is_dropped():
    raw = w.parse_hourly(raw_weather(2024, 11, duplicate={(3, 1)}))
    assert len(raw) == 721
    d = w.fill_missing_hours(raw, 2024, 11)
    assert len(d) == 720 and d["datetime"].is_unique and not d["weather_filled"].any()


def test_long_gap_is_not_papered_over():
    gap = {(5, h) for h in range(8, 14)}                                      # six missing hours
    d = w.fill_missing_hours(w.parse_hourly(raw_weather(2024, 1, drop=gap)), 2024, 1)
    assert len(d) == 744
    assert d["temp_c"].isna().sum() >= 2                                      # middle of the gap stays empty
    assert d["weather_filled"].sum() < 6


def test_quality_reports_filled_hours_and_march_panel_passes():
    weather = w.add_weather_flags(w.fill_missing_hours(w.parse_hourly(raw_weather(2024, 3, drop={(10, 2)})), 2024, 3))
    assert w.weather_quality(weather, 2024, 3)["filled_hours"] == 1
    taxi = pd.DataFrame({"datetime": [pd.Timestamp("2024-03-02 08:00")], "taxi_pickups": [5]})
    bike = pd.DataFrame({"hub_id": ["H01"], "datetime": [pd.Timestamp("2024-03-02 08:00")], "bike_starts": [2]})
    city = p.city_panel(taxi, bike, weather, 2024, 3)
    assert len(city) == 744 and city["temp_c"].notna().all()
    assert q.check_nulls(city, ["temp_c", "precip_mm"], "city")["status"] == "pass"
    assert "weather_filled" in city.columns
