"""Check which catalog sources are reachable and write a report.

Run this on YOUR machine (needs internet). It does not download data, only sends
a HEAD request to each landing page, and writes data/reference/source_check_report.csv.
Use the result to fill the 'last_verified' / 'status' columns of the catalog.
"""
import csv
import urllib.request
from datetime import date

from geopulse.config import REFERENCE_DIR
from geopulse.sources import load_catalog


def check(url: str, timeout: int = 15) -> str:
    if not url:
        return "no_url"
    try:
        req = urllib.request.Request(url, method="HEAD",
                                     headers={"User-Agent": "geopulse-intern-project"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return str(resp.status)
    except Exception as err:
        return f"error: {type(err).__name__}"


def main() -> None:
    df = load_catalog()
    out = REFERENCE_DIR / "source_check_report.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["source_id", "url_checked", "result", "checked_on"])
        for row in df.itertuples():
            url = row.landing_page
            result = check(url)
            print(f"{row.source_id:22s} {result}")
            writer.writerow([row.source_id, url, result, date.today().isoformat()])
    print(f"Report written to {out}")


if __name__ == "__main__":
    main()
