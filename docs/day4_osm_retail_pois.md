# Day 4 - Retail POIs from OpenStreetMap

## Goal
Day 3 gave us *movement* (taxi pickups). Day 4 adds *where the stores are*, so later days
can relate footfall to the retail mix around each hub.

## Steps
1. Build one Overpass query for shops and selected amenities inside the Manhattan bounding box.
2. Download once and cache the raw JSON (`data/raw/osm/`) so reruns do not hit the public API.
3. Parse nodes, ways and relations to one row per POI (centre point for ways/relations).
4. Clean: drop rows with no coordinates, outside the bbox, or duplicated (`osm_type` + `osm_id`).
5. Map OSM tags to 8 GeoPulse categories (see `SHOP_CATEGORY` / `AMENITY_CATEGORY`).
6. Assign each POI to its nearest hub and count POIs within 500 m of every hub.

## Run
```bash
source .venv/bin/activate
python scripts/ingest_osm.py              # add --refresh to re-download, --radius 300 to change catchment
```

## Outputs
| File | Committed? |
|------|-----------|
| data/raw/osm/osm_pois_raw.json | No |
| data/interim/osm_pois.csv | No |
| reports/tables/osm_category_counts.csv | Yes |
| reports/tables/osm_hub_summary.csv | Yes |
| reports/figures/osm_hub_poi_mix.png | Yes |
| data/reference/data_sources_catalog.csv (osm_pois marked verified) | Yes |

## Findings
_Fill in after running: total POIs, biggest category, which hub has the most POIs and the
highest density, and the share of POIs with a name / opening hours._

## Limitations
- OpenStreetMap is volunteer-edited: coverage and tagging vary by neighbourhood, so counts are
  indicative, not an official store register.
- Hub centres are approximate hand-picked points; a 500 m circle is a simple catchment, not a walking-time area.
- Category mapping is our own grouping; unknown shop types fall into `other_shop`.
- Public Overpass servers can be slow or rate-limit; the script retries and tries a second server.

## Attribution
(c) OpenStreetMap contributors, data under the Open Database Licence (ODbL).
