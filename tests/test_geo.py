import pytest

from geopulse.geo import haversine_m, nearest_hub
from geopulse.sources import get_hubs


def test_haversine_zero():
    assert haversine_m(40.75, -73.98, 40.75, -73.98) == 0


def test_haversine_one_degree_latitude():
    # 1 degree of latitude is about 111.2 km
    assert haversine_m(40.0, -74.0, 41.0, -74.0) == pytest.approx(111_195, rel=0.01)


def test_times_square_to_herald_square():
    d = haversine_m(40.7580, -73.9855, 40.7506, -73.9876)
    assert 700 < d < 950  # roughly 0.8 km


def test_nearest_hub():
    hubs = get_hubs()
    hub_id, dist = nearest_hub(40.7585, -73.9850, hubs)  # next to Times Square
    assert hub_id == "H01"
    assert dist < 100
