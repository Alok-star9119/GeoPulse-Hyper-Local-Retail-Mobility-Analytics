import pandas as pd
import pytest

from geopulse import ingest_tlc as t
from geopulse import sources


@pytest.fixture
def zones():
    return pd.DataFrame({
        "LocationID": [1, 4, 161, 237],
        "Borough": ["EWR", "Manhattan", "Manhattan", "Manhattan"],
        "Zone": ["Newark Airport", "Alphabet City", "Midtown Center", "Upper East Side South"],
        "service_zone": ["EWR", "Yellow Zone", "Yellow Zone", "Yellow Zone"],
    })


@pytest.fixture
def trips():
    # Small hand-made sample (NOT real TLC data) covering good and bad rows
    return pd.DataFrame({
        "tpep_pickup_datetime": pd.to_datetime([
            "2024-01-02 08:10", "2024-01-02 08:40", "2024-01-06 21:00",
            "2024-01-03 10:00", "2024-01-03 11:00", "2023-12-31 23:00", "2024-01-04 09:00"]),
        "tpep_dropoff_datetime": pd.to_datetime([
            "2024-01-02 08:30", "2024-01-02 09:00", "2024-01-06 21:20",
            "2024-01-03 09:00",   # dropoff before pickup
            "2024-01-03 11:30", "2024-01-01 00:10", "2024-01-04 09:20"]),
        "PULocationID": [161, 161, 237, 161, 1, 161, 4],
        "DOLocationID": [4, 237, 161, 4, 4, 4, 161],
        "passenger_count": [1, 2, 1, 1, 1, 1, 3],
        "trip_distance": [1.2, 2.0, 3.1, 1.0, 5.0, 1.0, 2.2],
        "total_amount": [12.5, 15.0, 20.0, 9.0, 40.0, 10.0, 14.0],
    })


def test_validate_counts_problems(trips):
    r = t.validate_trips(trips, 2024, 1)
    assert r["rows"] == 7
    assert r["pickup_outside_month"] == 1      # the 2023-12-31 row
    assert r["dropoff_before_pickup"] == 1


def test_basic_clean_removes_bad_rows(trips):
    clean = t.basic_clean(trips, 2024, 1)
    assert len(clean) == 5   # drops the Dec-2023 row and the negative-duration row


def test_filter_manhattan(trips, zones):
    clean = t.basic_clean(trips, 2024, 1)
    m = t.filter_manhattan_pickups(clean, zones)
    assert 1 not in set(m["PULocationID"])   # Newark airport excluded
    assert len(m) == 4


def test_hourly_profile(trips, zones):
    m = t.filter_manhattan_pickups(t.basic_clean(trips, 2024, 1), zones)
    p = t.hourly_profile(m, zones)
    row = p[(p.PULocationID == 161) & (p.day_type == "weekday") & (p.hour == 8)].iloc[0]
    # January 2024 has 23 weekdays and 8 weekend days
    assert row.pickups_total == 2 and row.days == 23 and row.avg_pickups == pytest.approx(0.09)
    assert p[p.day_type == "weekend"].days.iloc[0] == 8
    assert row.Zone == "Midtown Center"
    wk = p[p.day_type == "weekend"]
    assert wk.pickups_total.sum() == 1


def test_load_zones_requires_columns(tmp_path):
    f = tmp_path / "z.csv"
    f.write_text("LocationID,Borough\n1,EWR\n")
    with pytest.raises(ValueError):
        t.load_zones(f)


def test_parquet_roundtrip(trips, tmp_path):
    pytest.importorskip("pyarrow")
    f = tmp_path / "x.parquet"
    trips.to_parquet(f)
    assert len(t.load_trips(f)) == len(trips)


def test_mark_verified(tmp_path):
    copy = tmp_path / "cat.csv"
    copy.write_text(sources.CATALOG_PATH.read_text())
    sources.mark_verified("tlc_trips", path=copy, on="2026-11-12")
    df = sources.load_catalog(copy)
    row = df[df.source_id == "tlc_trips"].iloc[0]
    assert row.status == "verified" and row.last_verified == "2026-11-12"
    with pytest.raises(KeyError):
        sources.mark_verified("nope", path=copy)
