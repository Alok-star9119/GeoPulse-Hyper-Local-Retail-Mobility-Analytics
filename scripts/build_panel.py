"""Day 6: download weather and build the combined hourly datasets (taxi + bike + OSM + weather).

Run AFTER the Day 3, 4 and 5 scripts (and Day 8's map_zones_to_hubs.py, optional), same month:
  python scripts/ingest_tlc.py       --year 2024 --month 1
  python scripts/ingest_osm.py
  python scripts/ingest_citibike.py  --year 2024 --month 1
  python scripts/map_zones_to_hubs.py                     # Day 8: adds taxi to the hub panel
  python scripts/build_panel.py      --year 2024 --month 1

Outputs
  data/raw/weather/open_meteo_YYYY-MM.json            raw weather          (git-ignored)
  data/interim/citibike_agg_YYYY-MM.csv.gz            cached bike aggregate (git-ignored)
  reports/tables/weather_quality_YYYY-MM.json         weather checks       (committed)
  reports/tables/city_hourly_panel_YYYY-MM.csv        1 row per hour       (committed)
  reports/tables/hub_hourly_panel_YYYY-MM.csv         1 row per hub-hour   (committed)
  reports/tables/weather_effect_YYYY-MM.csv           % change in wet/freezing hours (committed)
  reports/tables/hub_mode_summary_YYYY-MM.csv         taxi vs bike per hub  (Day 8, committed)
  reports/figures/hub_taxi_vs_bike_YYYY-MM.png        taxi vs bike per hub  (Day 8, committed)
  reports/figures/weather_timeline_YYYY-MM.png, weather_effect_YYYY-MM.png (committed)
Weather data by Open-Meteo.com (CC BY 4.0).
"""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from geopulse.config import (FIGURES_DIR, INTERIM_DIR, RAW_DIR, REFERENCE_DIR, REPORTS_DIR,
                             ensure_directories)
from geopulse.ingest_citibike import assign_hubs, process_file, station_table
from geopulse.ingest_weather import (add_weather_flags, download_weather, fill_missing_hours,
                                     load_weather, weather_quality)
from geopulse.panel import (bike_hourly_by_hub, city_panel, daily_summary, hub_mode_summary,
                            hub_panel, taxi_hourly, taxi_hourly_by_hub, weather_effect)
from geopulse.sources import get_hubs, load_study_area, mark_verified


def load_taxi(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path, columns=["tpep_pickup_datetime", "PULocationID"])


def find_bike_file(year: int, month: int) -> Path:
    found = sorted((RAW_DIR / "citibike").glob(f"*{year}{month:02d}*"))
    found = [f for f in found if f.suffix in (".zip", ".csv")]
    if not found:
        raise SystemExit("Citi Bike file not found in data/raw/citibike/. "
                         "Run scripts/ingest_citibike.py first, or pass --bike-file.")
    return found[0]


def load_bike_agg(year: int, month: int, bbox: dict, bike_file: str | None) -> pd.DataFrame:
    cache = INTERIM_DIR / f"citibike_agg_{year}-{month:02d}.csv.gz"
    if cache.exists():
        return pd.read_csv(cache, dtype={"start_station_id": str, "start_station_name": str})
    agg, _ = process_file(Path(bike_file) if bike_file else find_bike_file(year, month),
                          bbox, year, month)
    agg.to_csv(cache, index=False)
    return agg


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2024)
    ap.add_argument("--month", type=int, default=1)
    ap.add_argument("--radius", type=float, default=500)
    ap.add_argument("--bike-file", help="Citi Bike zip/csv if not in data/raw/citibike")
    args = ap.parse_args()
    y, m = args.year, args.month
    ym = f"{y}-{m:02d}"

    ensure_directories()
    tables = REPORTS_DIR / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    area = load_study_area()
    hubs = get_hubs(area)

    # 1. weather
    weather = add_weather_flags(fill_missing_hours(load_weather(download_weather(y, m)), y, m))
    mark_verified("open_meteo")
    wq = weather_quality(weather, y, m)
    (tables / f"weather_quality_{ym}.json").write_text(json.dumps(wq, indent=2))
    print("Weather:", json.dumps(wq))

    # 2. taxi (Day 3 output)
    taxi_path = INTERIM_DIR / f"tlc_manhattan_{ym}.parquet"
    if not taxi_path.exists():
        raise SystemExit(f"{taxi_path.name} not found. Run scripts/ingest_tlc.py --year {y} --month {m} first.")
    trips = load_taxi(taxi_path)
    taxi_h = taxi_hourly(trips)

    # 3. bikes (Day 5 logic) -> hub-hour counts
    agg = load_bike_agg(y, m, area["bbox"], args.bike_file)
    stations = assign_hubs(station_table(agg), hubs, args.radius)
    bike_h = bike_hourly_by_hub(agg, stations)

    # 4. retail mix (Day 4 output), optional
    osm_path = tables / "osm_hub_summary.csv"
    osm = pd.read_csv(osm_path) if osm_path.exists() else None
    if osm is None:
        print("Note: osm_hub_summary.csv not found, hub panel will not include retail columns.")

    # 4b. taxi by hub (Day 8 zone -> hub map), optional
    zmap_path = REFERENCE_DIR / "zone_hub_map.csv"
    taxi_hub_h = None
    if zmap_path.exists():
        taxi_hub_h = taxi_hourly_by_hub(trips, pd.read_csv(zmap_path))
    else:
        print("Note: data/reference/zone_hub_map.csv not found. Run scripts/map_zones_to_hubs.py "
              "to add taxi pickups to the hub panel.")

    # 5. panels
    city = city_panel(taxi_h, bike_h, weather, y, m)
    hubp = hub_panel(bike_h, weather, hubs, y, m, osm, taxi_hub_h)
    city.to_csv(tables / f"city_hourly_panel_{ym}.csv", index=False)
    hubp.to_csv(tables / f"hub_hourly_panel_{ym}.csv", index=False)
    print(f"City panel {city.shape}, hub panel {hubp.shape}")

    # 5b. taxi vs bike per hub (Day 8)
    if taxi_hub_h is not None:
        mode = hub_mode_summary(hubp)
        mode.to_csv(tables / f"hub_mode_summary_{ym}.csv", index=False)
        print(mode.to_string(index=False))
        mp = mode.set_index("hub_name")[["taxi_pickups", "bike_starts"]]
        mp = mp.loc[mp.sum(axis=1).sort_values().index]
        ax = (mp.div(mp.sum(axis=1).replace(0, float("nan")), axis=0) * 100).plot(
            kind="barh", stacked=True, figsize=(9, 5.5), color=["#1b4f72", "#d95f02"])
        ax.set_xlabel("Share of taxi + bike trips (%)")
        ax.set_ylabel("")
        ax.set_title(f"Taxi vs bike mix by hub, {ym} (relative mix, see docs)")
        ax.figure.savefig(FIGURES_DIR / f"hub_taxi_vs_bike_{ym}.png", dpi=150, bbox_inches="tight")
        plt.close(ax.figure)

    # 6. weather effect (descriptive)
    metrics = ["taxi_pickups", "bike_starts_hubs"]
    eff = pd.concat([weather_effect(city, metrics, f) for f in ("is_wet", "is_cold")], ignore_index=True)
    eff.to_csv(tables / f"weather_effect_{ym}.csv", index=False)
    print(eff.to_string(index=False))

    # 7. charts
    d = daily_summary(city)
    fig, axs = plt.subplots(3, 1, figsize=(10, 8), sharex=True)
    axs[0].bar(d["date"], d["precip_mm"], color="#1b4f72")
    axs[0].set_ylabel("Precipitation (mm/day)")
    axs[1].plot(d["date"], d["temp_mean_c"], color="#d95f02", marker="o", ms=3)
    axs[1].axhline(0, color="grey", lw=0.8, ls="--")
    axs[1].set_ylabel("Mean temp (C)")
    for col, lab in (("taxi_pickups", "Taxi pickups"), ("bike_starts_hubs", "Bike starts (near hubs)")):
        axs[2].plot(d["date"], d[col] / d[col].mean() * 100, marker="o", ms=3, label=lab)
    axs[2].axhline(100, color="grey", lw=0.8, ls="--")
    axs[2].set_ylabel("Index (month mean = 100)")
    axs[2].legend(fontsize=8)
    axs[0].set_title(f"Daily weather and trips, {ym}")
    fig.autofmt_xdate()
    fig.savefig(FIGURES_DIR / f"weather_timeline_{ym}.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    lab = {"is_wet": "Wet hours (>= 0.1 mm)", "is_cold": "Freezing hours (<= 0 C)"}
    pv = eff.pivot(index="flag", columns="metric", values="change_pct").rename(index=lab)
    ax = pv.plot(kind="bar", figsize=(7, 4.5), color=["#d95f02", "#1b4f72"], rot=0)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_ylabel("% change vs comparable hours")
    ax.set_xlabel("")
    ax.set_title(f"Weather effect on trips, {ym} (descriptive)")
    ax.figure.savefig(FIGURES_DIR / f"weather_effect_{ym}.png", dpi=150, bbox_inches="tight")
    print("Done. Commit reports/ and data/reference/.")


if __name__ == "__main__":
    main()
