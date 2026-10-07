# Olist data pipeline

Reproducible ingestion, quality investigation, cleaning, analytical datasets,
PostgreSQL loading, a star schema, business analytics, and an interactive
dashboard for the Olist Brazilian E-Commerce dataset. The local pipeline also
includes Airflow orchestration, Spark/Pandas comparison, Kafka event replay,
and Docker Compose services. See [plan.md](plan.md) for phase status.

## Docker setup

With Docker Desktop running, follow the [local stack runbook](docs/local_stack.md)
to build images, run the full pipeline, open the dashboard and Airflow, and
verify PostgreSQL, Kafka, Spark, and the DAG. It includes PowerShell commands
and explains named volumes, generated credentials, and safe restarts.
See [verification results](docs/verification.md) for the full-data checks.

## Setup and reproduction

Use Python 3.13 and run these commands from the repository root (PowerShell):

```shell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pip install -r requirements-analytics.txt
```

Place the nine original Olist CSVs in `data/raw/`; expected filenames
are listed in `src/ingestion/csv_ingestion.py`. Raw files are never overwritten.

```shell
.venv\Scripts\python.exe -m src.ingestion.csv_ingestion
.venv\Scripts\python.exe -m src.cleaning.pipeline
.venv\Scripts\python.exe -m src.transformation.transformations
.venv\Scripts\python.exe -m src.analytics.reports
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

If cleaned Parquet files already exist, only the transformation command is
needed. An alternate processed directory can be supplied with `--processed-dir`.
The cleaning command intentionally regenerates the nine cleaned outputs; the
transformation command regenerates only their analytical subdirectory.

For interactive exploration, use notebooks 01–04, then `05_analytics.ipynb`, selecting the
virtual environment as the kernel. Notebook 03 verifies cleaned Parquet
round trips. Notebook 04 inspects join cardinality, missing child rows,
engineered features, reconciliation, and verified analytical exports. Notebook
05 answers sales, customer, logistics, and review questions and exports
delivered-order reports.

## PostgreSQL and warehouse

Use a local PostgreSQL 17+ database, or Docker Compose if Docker is installed.
Set connection values for your own local database (replace the password):

```powershell
$env:PGHOST = '127.0.0.1'
$env:PGPORT = '5432'
$env:PGDATABASE = 'olist'
$env:PGUSER = 'olist'
$env:PGPASSWORD = '<your-local-password>'
# Optional: start the supplied database container.
docker compose -f docker/docker-compose.yml up -d --wait

.venv\Scripts\python.exe -m src.database.loader
.venv\Scripts\python.exe -m src.database.warehouse
.venv\Scripts\python.exe -m src.database.validation
```

With an existing PostgreSQL installation, create the named database/user first
and omit the Docker command. `DATABASE_URL` is also supported. Python reads
environment variables, not `.env` automatically; Compose can use
`--env-file .env`. Never commit real credentials.

The loader refuses populated tables by default. An intentional full reload uses
`python -m src.database.loader --replace`, followed by the warehouse refresh.
Loads and warehouse refreshes are transactional. PostgreSQL tables use explicit
keys/constraints, decimal currency, nullable dates, and preserved quality flags.
SQL practice queries live under `sql/queries/`.

All nine cleaned tables, the order view, five SQL reports, and both warehouse
facts have SQL/Pandas integration checks. Compose provides a persistent local
PostgreSQL service. See [database design and integration tests](docs/database_design.md)
and the [container runbook](docs/local_stack.md).

## Dashboard

```powershell
.venv\Scripts\python.exe -m streamlit run dashboards/app.py --server.address 127.0.0.1
```

Open the local URL printed by Streamlit. The five views cover overview, sales,
customers, logistics, and reviews. Shared status/date filters apply to all
metrics and downloads; delivered orders are selected by default. The dashboard
uses curated Parquet and runs without a database. See
[dashboard instructions](dashboards/README.md) for an alternate data directory
and Power BI use of exported CSVs.

## Validation

The test suite covers transformations, cleaning persistence, analytical
denominators/cohorts, dashboard navigation/filters, and database integration.
Database tests run when `OLIST_TEST_DATABASE_URL` names a dedicated disposable
database ending in `_test`; otherwise they are explicitly skipped.
The isolated PostgreSQL helper in `scripts/verify_postgres.py` runs them and
validates the full dataset without touching an existing server.

## Outputs

| File under `data/processed/analytical/` | Grain | Current rows |
| --- | --- | ---: |
| `orders.parquet` | One order | 99,441 |
| `customers.parquet` | One `customer_unique_id` | 96,096 |
| `products.parquet` | One product | 32,951 |
| `reconciliation.csv` | One validation check | 20 |

Business report CSVs are under `data/processed/reports/` (all statuses), with
notebook outputs under `reports/delivered/`. Database and warehouse evidence
is saved as `database_validation.csv` (15 checks) and
`warehouse_validation.csv` (9 checks). These files describe the last verification
run, not a continuously monitored server.

All statuses are retained. Item value (13,591,643.70 BRL), freight
(2,251,909.54 BRL), and recorded payments (16,008,872.12 BRL) reconcile to
their own cleaned sources. These are gross recorded amounts, not net realized
revenue. Missing child data and ratings remain unknown; negative delivery
intervals and cleaning flags remain visible. Product ratings are order-level
reviews associated with products, not independent product reviews.

See [the data dictionary](docs/data_dictionary.md),
[cleaning decisions](docs/cleaning_decisions.md),
[transformation design](docs/transformation_design.md), and
[architecture](docs/architecture.md) for assumptions and validation details.
The executed analysis is summarized in [analytics findings](docs/analytics_findings.md).
See [the local stack runbook](docs/local_stack.md) for expanded testing, Airflow,
Spark, Kafka, and the containerized stack. Optional cloud deployment and
machine learning remain deferred.
