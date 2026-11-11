"""Plot the Manhattan study area bounding box and retail hubs -> reports/figures."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from geopulse.config import FIGURES_DIR, ensure_directories
from geopulse.sources import load_study_area


LABEL_LEFT = {"H02"}  # hubs whose label goes to the left to avoid overlap


def main() -> None:
    ensure_directories()
    area = load_study_area()
    b = area["bbox"]
    fig, ax = plt.subplots(figsize=(6, 9))
    ax.plot([b["min_lon"], b["max_lon"], b["max_lon"], b["min_lon"], b["min_lon"]],
            [b["min_lat"], b["min_lat"], b["max_lat"], b["max_lat"], b["min_lat"]],
            color="grey", linestyle="--", label="Study area bounding box")
    for h in area["hubs"]:
        ax.scatter(h["lon"], h["lat"], s=60, color="#1f4e79", zorder=3)
        left = h["hub_id"] in LABEL_LEFT
        ax.annotate(h["name"], (h["lon"], h["lat"]),
                    xytext=(-7, -10) if left else (6, 4),
                    ha="right" if left else "left",
                    textcoords="offset points", fontsize=8)
    ax.set_title("GeoPulse study area: Manhattan retail hubs (approximate)")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_aspect(1 / 0.76)  # approx lon/lat scale at 40.7 N
    ax.legend(loc="lower right", fontsize=8)
    ax.grid(alpha=0.3)
    out = FIGURES_DIR / "study_area_hubs.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    print(f"Saved {out}")


if __name__ == "__main__":
    main()
