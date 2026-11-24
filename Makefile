# Shortcuts for common tasks. Usage: make <target>   (activate the venv first)
PY ?= python
YEAR ?= 2024
MONTH ?= 1
MONTHS ?= 2024-02 2024-03

.PHONY: test check month months compare forecast dashboard numbers

test:       ## run the unit tests
	$(PY) -m pytest -q

check:      ## repository hygiene check
	$(PY) scripts/check_repo.py

month:      ## panel, quality review, EDA and retail analysis for one month (needs the Day 3-5 inputs)
	$(PY) scripts/build_panel.py --year $(YEAR) --month $(MONTH)
	$(PY) scripts/quality_review.py --year $(YEAR) --month $(MONTH)
	$(PY) scripts/eda_hub_rhythm.py --year $(YEAR) --month $(MONTH)
	$(PY) scripts/retail_vs_mobility.py --year $(YEAR) --month $(MONTH)

months:     ## full pipeline for MONTHS (downloads data)
	$(PY) scripts/run_months.py --months $(MONTHS)

compare:    ## cross-month comparison
	$(PY) scripts/compare_months.py

forecast:   ## baseline forecasts for one month
	$(PY) scripts/forecast_baseline.py --year $(YEAR) --month $(MONTH)

dashboard:  ## offline HTML dashboard
	$(PY) scripts/build_dashboard.py

numbers:    ## headline numbers for the summary
	$(PY) scripts/week2_key_numbers.py
