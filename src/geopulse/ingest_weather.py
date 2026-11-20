"""Day 6: hourly weather for Manhattan from the Open-Meteo historical (archive) API.

Open-Meteo data is licensed CC BY 4.0 (https://open-meteo.com/en/license), so cite it.
All timestamps are requested in America/New_York local time to match the taxi and
bike data, which are also in local time.
"""
from __future__ import annotations

import calendar
import json
import urllib.parse
from pathlib import Path

import pandas as pd

from geopulse.config import RAW_DIR
from geopulse.download import download_file
from geopulse.logger import get_logger

log = get_logger(__name__)

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
WEATHER_RAW_DIR = RAW_DIR / "weather"
CENTER = (40.7831, -73.9712)   # approx. centre of Manhattan (lat, lon)

API_VARIABLES = ["temperature_2m", "precipitation", "rain", "snowfall",
                 "wind_speed_10m", "weather_code"]
RENAME = {"temperature_2m": "temp_c", "precipitation": "precip_mm", "rain": "rain_mm",
          "snowfall": "snow_cm", "wind_speed_10m": "wind_kmh", "weather_code": "weather_code"}

WET_MM = 0.1      # an hour with at least this much precipitation counts as wet
COLD_C = 0.0      # an hour at or below this temperature counts as freezing


def build_url(year: int, month: int, lat: float = CENTER[0], lon: float = CENTER[1],
              base: str = ARCHIVE_URL) -> str:
    last = calendar.monthrange(year, month)[1]
    params = {
        "latitude": lat, "longitude": lon,
        "start_date": f"{year}-{month:02d}-01", "end_date": f"{year}-{month:02d}-{last:02d}",
        "hourly": ",".join(API_VARIABLES), "timezone": "America/New_York",
    }
    return f"{base}?{urllib.parse.urlencode(params)}"


def download_weather(year: int, month: int, base: str = ARCHIVE_URL) -> Path:
    dest = WEATHER_RAW_DIR / f"open_meteo_{year}-{month:02d}.json"
    return download_file(build_url(year, month, base=base), dest, retries=3)


def parse_hourly(data: dict) -> pd.DataFrame:
    """Open-Meteo JSON -> one row per hour with friendly column names."""
    if "hourly" not in data or "time" not in data["hourly"]:
        raise ValueError(f"Unexpected Open-Meteo response: {str(data)[:200]}")
    h = data["hourly"]
    df = pd.DataFrame({"datetime": pd.to_datetime(h["time"])})
    for api_name, name in RENAME.items():
        if api_name not in h:
            raise ValueError(f"Open-Meteo response is missing '{api_name}'")
        df[name] = h[api_name]
    return df


def load_weather(path: Path) -> pd.DataFrame:
    return parse_hourly(json.loads(Path(path).read_text(encoding="utf-8")))


MAX_FILL_HOURS = 2     # gaps longer than this are left empty so the quality review can flag them


def fill_missing_hours(df: pd.DataFrame, year: int, month: int) -> pd.DataFrame:
    """Return exactly one row per hour of the month, filling tiny gaps and marking them.

    Daylight-saving changes make local-time data awkward: the clock skips 02:00 in March and
    repeats 01:00 in November. Duplicated hours are dropped (first kept); gaps of up to
    MAX_FILL_HOURS hours are filled by interpolation; every filled hour has weather_filled = True.
    """
    n = calendar.monthrange(year, month)[1] * 24
    grid = pd.date_range(f"{year}-{month:02d}-01", periods=n, freq="h", name="datetime")
    d = df.drop_duplicates(subset="datetime").set_index("datetime").reindex(grid)
    missing = d["temp_c"].isna()
    num = [c for c in d.columns if c != "weather_code"]
    d[num] = d[num].astype(float).interpolate(limit=MAX_FILL_HOURS, limit_direction="both")
    d["weather_code"] = d["weather_code"].ffill(limit=MAX_FILL_HOURS).bfill(limit=MAX_FILL_HOURS)
    d["weather_filled"] = missing & d["temp_c"].notna()
    return d.reset_index()


def add_weather_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Add simple boolean flags used for the weather-effect analysis."""
    out = df.copy()
    out["is_wet"] = out["precip_mm"].fillna(0) >= WET_MM
    out["is_snow"] = out["snow_cm"].fillna(0) > 0
    out["is_cold"] = out["temp_c"] <= COLD_C
    return out


def weather_quality(df: pd.DataFrame, year: int, month: int) -> dict:
    expected = calendar.monthrange(year, month)[1] * 24
    return {
        "rows": int(len(df)), "expected_rows": expected,
        "null_counts": {c: int(v) for c, v in df.isna().sum().items() if v > 0},
        "temp_min_c": float(df["temp_c"].min()), "temp_max_c": float(df["temp_c"].max()),
        "precip_total_mm": round(float(df["precip_mm"].sum()), 1),
        "wet_hours": int((df["precip_mm"] >= WET_MM).sum()),
        "freezing_hours": int((df["temp_c"] <= COLD_C).sum()),
        "filled_hours": int(df["weather_filled"].sum()) if "weather_filled" in df.columns else 0,
    }
