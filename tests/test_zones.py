import zipfile

import pandas as pd
import pytest

from geopulse import zones as z
from geopulse.sources import ensure_source, get_hubs, load_catalog

HUBS = get_hubs()


def tables(dist: dict, cdist: dict | None = None):
    """Build boundary/centre distance tables for zones given {zone_id: {hub_id: metres}}."""
    ids = list(dist)
    cols = [h.hub_id for h in HUBS]
    b = pd.DataFrame([[dist[i].get(c, 9999.0) for c in cols] for i in ids], index=ids, columns=cols)
    cdist = cdist or {}
    c = pd.DataFrame([[cdist.get(i, {}).get(col, 9999.0) for col in cols] for i in ids], index=ids, columns=cols)
    return b, c


def test_assignment_basic_and_radius():
    b, c = tables({1: {"H01": 0.0, "H02": 800.0},      # inside Times Square zone
                   2: {"H02": 420.0, "H03": 900.0},    # near Herald Square
                   3: {"H05": 650.0}})                 # too far from every hub
    m = z.assign_zones_to_hubs(b, c, radius_m=500).set_index("LocationID")
    assert m.loc[1, "hub_id"] == "H01" and m.loc[1, "contains_hub"]
    assert m.loc[2, "hub_id"] == "H02" and not m.loc[2, "contains_hub"]
    assert pd.isna(m.loc[3, "hub_id"]) and m.loc[3, "nearest_hub_id"] == "H05"


def test_tie_broken_by_centroid_distance():
    b, c = tables({7: {"H01": 0.0, "H02": 0.0}}, {7: {"H01": 400.0, "H02": 150.0}})
    m = z.assign_zones_to_hubs(b, c).set_index("LocationID")
    assert m.loc[7, "hub_id"] == "H02"                  # both hubs inside; the nearer centre wins


def test_each_zone_gets_at_most_one_hub():
    b, c = tables({1: {"H01": 10.0, "H02": 20.0, "H03": 30.0}, 2: {"H02": 5.0}})
    m = z.assign_zones_to_hubs(b, c)
    assert m["LocationID"].is_unique and len(m) == 2


def test_mismatched_tables_rejected():
    b, c = tables({1: {"H01": 0.0}})
    with pytest.raises(ValueError):
        z.assign_zones_to_hubs(b, c.rename(index={1: 99}))


def test_mapping_report_shows_hubs_without_zones():
    m = pd.DataFrame({"hub_id": ["H01", "H01", None], "contains_hub": [True, False, False]})
    r = z.mapping_report(m, HUBS).set_index("hub_id")
    assert r.loc["H01", "zones_assigned"] == 2 and r.loc["H01", "zones_containing_hub"] == 1
    assert r.loc["H10", "zones_assigned"] == 0


def test_extract_shapes(tmp_path):
    zp = tmp_path / "taxi_zones.zip"
    with zipfile.ZipFile(zp, "w") as zf:
        zf.writestr("taxi_zones/taxi_zones.shp", b"x")
        zf.writestr("taxi_zones/taxi_zones.dbf", b"x")
    assert z.extract_shapes(zp).name == "taxi_zones.shp"
    empty = tmp_path / "empty.zip"
    with zipfile.ZipFile(empty, "w") as zf:
        zf.writestr("readme.txt", "no shapes")
    with pytest.raises(ValueError):
        z.extract_shapes(empty)


def test_ensure_source_adds_once(tmp_path):
    cat = tmp_path / "cat.csv"
    cat.write_text(load_catalog().to_csv(index=False))
    row = {"source_id": "tlc_zone_shapes", "name": "TLC taxi zone shapes", "category": "reference",
           "role": "zone polygons", "priority": "secondary", "granularity": "zone",
           "file_format": "shapefile_zip", "access_method": "direct_download", "status": "unverified"}
    assert ensure_source(row, cat) is True
    assert ensure_source(row, cat) is False
    assert "tlc_zone_shapes" in set(load_catalog(cat)["source_id"])


# ---- geometry tests: need geopandas (installed from requirements.txt); skipped otherwise ----
def square(lon, lat, half=0.002):
    from shapely.geometry import box
    return box(lon - half, lat - half, lon + half, lat + half)


@pytest.fixture
def toy_zones():
    gpd = pytest.importorskip("geopandas")
    pytest.importorskip("shapely")
    h = {x.hub_id: x for x in HUBS}
    return gpd.GeoDataFrame({
        "LocationID": [1, 2, 3],
        "zone": ["Around Times Sq", "Around Herald Sq", "Far north"],
        "borough": ["Manhattan"] * 3,
        "geometry": [square(h["H01"].lon, h["H01"].lat),
                     square(h["H02"].lon, h["H02"].lat),
                     square(-73.93, 40.87)]}, crs="EPSG:4326")


def test_geometry_distances(toy_zones):
    b, c = z.zone_hub_distances(toy_zones, HUBS)
    assert b.loc[1, "H01"] == 0 and b.loc[2, "H02"] == 0           # hub inside its own square
    assert b.loc[1, "H02"] > 300                                   # Herald Sq is ~800 m away
    assert c.loc[1, "H01"] < 5                                     # hub is at the square's centre
    assert b.loc[3].min() > 500


def test_geometry_full_table(toy_zones):
    t = z.zone_hub_table(toy_zones, HUBS, radius_m=500).set_index("LocationID")
    assert t.loc[1, "hub_id"] == "H01" and t.loc[2, "hub_id"] == "H02"
    assert pd.isna(t.loc[3, "hub_id"])
    assert t.loc[1, "zone"] == "Around Times Sq"
