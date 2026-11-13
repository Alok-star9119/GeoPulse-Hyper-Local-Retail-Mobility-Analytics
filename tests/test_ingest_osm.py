import http.server
import json
import threading

import pandas as pd
import pytest

from geopulse import ingest_osm as o
from geopulse.geo import haversine_m, haversine_m_array
from geopulse.sources import get_hubs, load_study_area

# Hand-made Overpass-style response (NOT real OSM data)
FAKE = {"elements": [
    {"type": "node", "id": 1, "lat": 40.7581, "lon": -73.9856,
     "tags": {"shop": "clothes", "name": "A Fashion", "opening_hours": "Mo-Su 10:00-21:00"}},
    {"type": "way", "id": 2, "center": {"lat": 40.7579, "lon": -73.9850},
     "tags": {"amenity": "cafe", "name": "B Cafe"}},
    {"type": "node", "id": 3, "lat": 40.7506, "lon": -73.9877, "tags": {"shop": "supermarket"}},
    {"type": "node", "id": 3, "lat": 40.7506, "lon": -73.9877, "tags": {"shop": "supermarket"}},   # duplicate
    {"type": "node", "id": 4, "lat": 41.5, "lon": -73.9, "tags": {"shop": "gift"}},                 # outside bbox
    {"type": "relation", "id": 5, "tags": {"shop": "mall"}},                                         # no coordinates
    {"type": "node", "id": 6, "lat": 40.7240, "lon": -74.0030, "tags": {"shop": "weirdnewtype"}},
]}


@pytest.fixture
def area():
    return load_study_area()


def test_build_query_contains_bbox(area):
    q = o.build_query(area["bbox"])
    assert "(40.698,-74.022,40.882,-73.907)" in q
    assert 'nwr["shop"]' in q and "out center tags;" in q


def test_parse_uses_center_for_ways():
    df = o.parse_elements(FAKE)
    assert len(df) == 7
    assert df.loc[df.osm_id == 2, "lat"].iloc[0] == pytest.approx(40.7579)
    assert df.loc[df.osm_id == 1, "has_opening_hours"].iloc[0]


def test_categorise():
    assert o.categorise("clothes", None) == "fashion"
    assert o.categorise(None, "cafe") == "food_beverage"
    assert o.categorise("weirdnewtype", None) == "other_shop"
    assert o.categorise(float("nan"), float("nan")) == "other_shop"


def test_clean_pois(area):
    c = o.clean_pois(o.parse_elements(FAKE), area["bbox"])
    assert sorted(c.osm_id) == [1, 2, 3, 6]      # drops duplicate, outside-bbox, no-coords
    assert set(c.category) == {"fashion", "food_beverage", "food_retail", "other_shop"}


def test_nearest_hub_and_summary(area):
    hubs = get_hubs(area)
    c = o.assign_nearest_hub(o.clean_pois(o.parse_elements(FAKE), area["bbox"]), hubs)
    assert c.loc[c.osm_id == 1, "nearest_hub_id"].iloc[0] == "H01"      # Times Square
    assert c.loc[c.osm_id == 3, "nearest_hub_id"].iloc[0] == "H02"      # Herald Square
    s = o.hub_summary(c, hubs, radius_m=500).set_index("hub_id")
    assert s.loc["H01", "poi_total"] == 2
    assert s.loc["H01", "fashion"] == 1 and s.loc["H01", "food_beverage"] == 1
    assert s.loc["H10", "poi_total"] == 0


def test_category_counts(area):
    c = o.clean_pois(o.parse_elements(FAKE), area["bbox"])
    cc = o.category_counts(c).set_index("category")
    assert cc.loc["fashion", "opening_hours_share"] == 1.0
    assert cc.loc["food_beverage", "named_share"] == 1.0
    assert cc["poi_count"].sum() == 4


def test_vectorised_distance_matches_scalar():
    d = haversine_m_array([40.7580, 40.7359], [-73.9855, -73.9911], 40.7506, -73.9876)
    assert d[0] == pytest.approx(haversine_m(40.7580, -73.9855, 40.7506, -73.9876), rel=1e-9)
    assert d[1] == pytest.approx(haversine_m(40.7359, -73.9911, 40.7506, -73.9876), rel=1e-9)


@pytest.fixture
def overpass_server():
    class H(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            n = int(self.headers["Content-Length"])
            self.rfile.read(n)
            body = json.dumps(FAKE).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *a):
            pass
    httpd = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}/"
    httpd.shutdown()


def test_fetch_overpass_local_server(overpass_server, area):
    data = o.fetch_overpass(o.build_query(area["bbox"]), urls=[overpass_server], retries=1)
    assert len(data["elements"]) == 7


def test_fetch_failure_raises(monkeypatch):
    monkeypatch.setattr("geopulse.ingest_osm.time.sleep", lambda s: None)
    with pytest.raises(RuntimeError):
        o.fetch_overpass("x", urls=["http://127.0.0.1:9/"], retries=1, timeout=2)
