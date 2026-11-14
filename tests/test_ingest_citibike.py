import zipfile

import numpy as np
import pandas as pd
import pytest

from geopulse import ingest_citibike as c
from geopulse.sources import get_hubs, load_study_area

CSV_HEADER = "ride_id,started_at,ended_at,start_station_name,start_station_id,start_lat,start_lng,member_casual\n"
# Hand-made rows (NOT real Citi Bike data)
ROWS = [
    # good: weekday 08:xx near Times Square
    "r1,2024-01-02 08:10:00,2024-01-02 08:25:00,Broadway & W 45 St,6500.1,40.7581,-73.9856,member",
    "r2,2024-01-02 08:40:00,2024-01-02 08:50:00,Broadway & W 45 St,6500.1,40.7583,-73.9854,casual",
    # good: weekend 14:xx near Herald Square
    "r3,2024-01-06 14:00:00,2024-01-06 14:30:00,W 34 St & 6 Ave,6300.2,40.7506,-73.9877,casual",
    # bad: 30-second trip
    "r4,2024-01-03 09:00:00,2024-01-03 09:00:30,Broadway & W 45 St,6500.1,40.7581,-73.9856,member",
    # bad: outside month
    "r5,2023-12-31 23:00:00,2024-01-01 00:10:00,Broadway & W 45 St,6500.1,40.7581,-73.9856,member",
    # bad: outside bbox (New Jersey)
    "r6,2024-01-03 10:00:00,2024-01-03 10:20:00,Hoboken Terminal,HB101,40.735,-74.03,member",
    # bad: missing station id
    "r7,2024-01-03 11:00:00,2024-01-03 11:20:00,,,40.7581,-73.9856,member",
    # bad: end before start
    "r8,2024-01-03 12:30:00,2024-01-03 12:00:00,Broadway & W 45 St,6500.1,40.7581,-73.9856,member",
]


@pytest.fixture
def area():
    return load_study_area()


@pytest.fixture
def csv_zip(tmp_path):
    p = tmp_path / "202401-citibike-tripdata.zip"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("202401-citibike-tripdata_1.csv", CSV_HEADER + "\n".join(ROWS[:4]) + "\n")
        zf.writestr("202401-citibike-tripdata_2.csv", CSV_HEADER + "\n".join(ROWS[4:]) + "\n")
        zf.writestr("__MACOSX/._junk.csv", "garbage")
    return p


def test_candidate_urls():
    urls = c.candidate_urls(2024, 3)
    assert urls[0].endswith("202403-citibike-tripdata.csv.zip")
    assert urls[1].endswith("202403-citibike-tripdata.zip")


def test_calendar_day_counts():
    assert c.calendar_day_counts(2024, 1) == {"weekday": 23, "weekend": 8}
    assert c.calendar_day_counts(2024, 2) == {"weekday": 21, "weekend": 8}


def test_process_zip_with_two_csvs(csv_zip, area):
    agg, rep = c.process_file(csv_zip, area["bbox"], 2024, 1, chunksize=3)
    assert rep["rows_read"] == 8 and rep["rows_kept"] == 3 and rep["rows_removed"] == 5
    assert agg["trips"].sum() == 3
    assert set(agg["user_type"]) == {"member", "casual"}


def test_old_schema_is_renamed(tmp_path, area):
    f = tmp_path / "old.csv"
    f.write_text("tripduration,starttime,stoptime,start station id,start station name,"
                 "start station latitude,start station longitude,usertype\n"
                 "900,2024-01-02 08:10:00,2024-01-02 08:25:00,6500.1,Broadway,40.7581,-73.9856,Subscriber\n")
    agg, rep = c.process_file(f, area["bbox"], 2024, 1)
    assert rep["rows_kept"] == 1 and agg["user_type"].iloc[0] == "member"


def test_missing_columns_raises(tmp_path, area):
    f = tmp_path / "bad.csv"
    f.write_text("a,b\n1,2\n")
    with pytest.raises(ValueError):
        c.process_file(f, area["bbox"], 2024, 1)


def test_station_table_and_hubs(csv_zip, area):
    hubs = get_hubs(area)
    agg, _ = c.process_file(csv_zip, area["bbox"], 2024, 1)
    st = c.assign_hubs(c.station_table(agg), hubs, 500).set_index("station_id")
    assert st.loc["6500.1", "trips"] == 2
    assert st.loc["6500.1", "casual_share"] == pytest.approx(0.5)
    assert st.loc["6500.1", "hub_id"] == "H01"
    assert st.loc["6300.2", "hub_id"] == "H02"
    assert st.loc["6300.2", "nearest_hub_m"] < 100


def test_station_beyond_radius_has_no_hub(area):
    hubs = get_hubs(area)
    st = pd.DataFrame({"station_id": ["x"], "station_name": ["far"], "trips": [5],
                       "lat": [40.790], "lon": [-73.975], "casual_share": [0.0]})  # Upper West Side
    out = c.assign_hubs(st, hubs, radius_m=500)
    assert out["hub_id"].isna().all()


def test_hub_profile_and_summary(csv_zip, area):
    hubs = get_hubs(area)
    agg, _ = c.process_file(csv_zip, area["bbox"], 2024, 1)
    st = c.assign_hubs(c.station_table(agg), hubs, 500)
    prof = c.hub_hourly_profile(agg, st, 2024, 1)
    row = prof[(prof.hub_id == "H01") & (prof.day_type == "weekday") & (prof.hour == 8)].iloc[0]
    assert row.trips_total == 2 and row.days == 23 and row.avg_trips == pytest.approx(0.09)
    summ = c.hub_summary(st, prof, hubs).set_index("hub_id")
    assert summ.loc["H01", "trips"] == 2 and summ.loc["H01", "weekday_peak_hour"] == 8
    assert summ.loc["H01", "casual_share"] == pytest.approx(0.5)
    assert summ.loc["H10", "stations"] == 0 and pd.isna(summ.loc["H10", "weekday_peak_hour"])


def test_compare_hourly_identical_profiles_correlate_perfectly():
    hours = np.arange(24)
    vals = np.exp(-((hours - 8.5) ** 2) / 10) + 0.3 * np.exp(-((hours - 18) ** 2) / 8)
    bike = pd.DataFrame({"day_type": "weekday", "hour": hours, "avg_trips": vals})
    taxi = pd.DataFrame({"day_type": "weekday", "hour": hours, "avg_pickups": vals * 50})
    cmp_df, corr = c.compare_hourly(bike, taxi)
    assert corr == pytest.approx(1.0)
    assert cmp_df["bike_share"].sum() == pytest.approx(1.0, abs=0.01)


def test_combine_aggregates_merges_same_key(area):
    a = pd.DataFrame({"start_station_id": ["1"], "start_station_name": ["A"], "date": ["2024-01-02"],
                      "hour": [8], "user_type": ["member"], "trips": [2], "lat_sum": [80.0], "lng_sum": [-147.0]})
    out = c.combine_aggregates([a, a])
    assert len(out) == 1 and out["trips"].iloc[0] == 4
    with pytest.raises(ValueError):
        c.combine_aggregates([])
