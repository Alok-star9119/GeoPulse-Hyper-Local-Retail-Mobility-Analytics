# Day 12: Offline HTML Dashboard

## Why
The internship asks for dashboards a mentor can open without running code. Days 5-11 produced many CSV
tables and PNG figures; Day 12 gathers the key ones on one page.

## What was added
| Item | Purpose |
|---|---|
| `src/geopulse/dashboard.py` | Builds one HTML file: KPI cards, month-by-month bars, hub tables (taxi and bike), weekday hourly rhythm lines, weather-effect table, retail-mobility correlation consistency. Charts are inline SVG; no JavaScript, no internet, light and dark mode. |
| `scripts/build_dashboard.py` | `python scripts/build_dashboard.py [--months ...]` writes `reports/dashboard.html`. |
| `tests/test_dashboard.py` | Page contains no scripts or external links, text is HTML-escaped, NaN breaks lines, missing tables do not crash. |
| `multimonth.correlation_consistency` | Fixed: it crashed on an empty correlation table (found by the dashboard test). |

## How to run
```bash
python scripts/build_dashboard.py
xdg-open reports/dashboard.html
```

## Reading it
- A hub with "no data" has no Citi Bike station or taxi zone in its catchment; it is not zero demand.
- With one month the "Month by month" section is left out; "Consistent" correlations need 2+ months.
- All numbers are descriptive; nothing on the page is causal.

## Findings
_Open the dashboard on real data and write 3-4 sentences: what a mentor should notice first, and one thing the page cannot show._

## Limitations
- Charts are static (no hover or filters); interactivity would need a JavaScript library.
- Only the top 5 hubs by volume are drawn in the rhythm charts to stay readable.
