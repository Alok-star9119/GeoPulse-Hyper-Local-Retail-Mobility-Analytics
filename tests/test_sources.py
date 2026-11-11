import pandas as pd
import pytest

from geopulse import sources


def test_catalog_loads_and_is_valid():
    df = sources.load_catalog()
    assert len(df) >= 6
    assert {"tlc_trips", "citibike_trips", "osm_pois", "synthetic_footfall"} <= set(df["source_id"])


def test_catalog_rejects_duplicates():
    df = sources.load_catalog()
    bad = pd.concat([df, df.iloc[[0]]])
    with pytest.raises(ValueError):
        sources.validate_catalog(bad)


def test_catalog_rejects_missing_column():
    df = sources.load_catalog().drop(columns=["licence"])
    with pytest.raises(ValueError):
        sources.validate_catalog(df)


def test_study_area_hubs_inside_bbox():
    area = sources.load_study_area()
    assert len(area["hubs"]) == 10
    for h in area["hubs"]:
        assert sources.in_bbox(h["lat"], h["lon"], area["bbox"])


def test_tlc_url():
    url = sources.tlc_trip_url(2024, 3)
    assert url.endswith("yellow_tripdata_2024-03.parquet")
    with pytest.raises(ValueError):
        sources.tlc_trip_url(2024, 13)
