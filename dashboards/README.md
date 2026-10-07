# Olist commerce dashboard

Run from the repository root after generating the phase 5 analytical outputs:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-analytics.txt
.venv\Scripts\python.exe -m streamlit run dashboards/app.py --server.address 127.0.0.1
```

Open the local URL printed by Streamlit (normally http://localhost:8501).
The dashboard reads curated Parquet plus cleaned item/seller lookups; a live
database is not required. Set `OLIST_PROCESSED_DIR` to use another processed
directory. Cached data refreshes when any input file's timestamp/size changes.

The five views are Overview, Sales, Customers, Logistics, and Reviews. Status
and inclusive purchase-date filters apply consistently to all metrics,
charts, and CSV downloads. Delivered orders are selected by default. Empty
selections and missing data have explicit messages.

Revenue is recorded item price excluding freight. Average order payment
uses known payment totals, and late rate uses known delivery outcomes.
Repeat customers and acquisition cohorts are measured within the current
selection, not lifetime history. Delivery comparisons are associations, and
product/category scores inherit whole-order reviews.

Streamlit is the runnable repository dashboard. For Power BI, use exported
CSVs under `data/processed/reports/`, or connect to PostgreSQL's warehouse.
Recommended relationships are one-to-many from dimensions to facts. Keep
order and item measures on their own facts to avoid duplicated payments.
No proprietary `.pbix` file is generated.

All views and filtering behavior are covered by Streamlit's
[AppTest](https://docs.streamlit.io/develop/api-reference/app-testing) tests.
