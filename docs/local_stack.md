# Run the local Docker stack

Run these PowerShell commands from the repository root with Docker Desktop's
Linux engine running. The first build downloads Python, Airflow, Kafka, Spark,
and Java dependencies and can take several minutes. Keep the nine original
Olist CSVs in `data/raw/`; containers mount them read-only.

## Configure and build

```powershell
# Only needed if .env does not already exist; existing credentials are preserved.
python scripts/configure_local.py
$base = @('--env-file', '.env', '-f', 'docker/docker-compose.yml')
$stack = $base + @('-f', 'docker/docker-compose.airflow.yml')
docker compose @stack config --quiet
docker compose @stack build pipeline spark airflow-init
```

The ignored `.env` contains generated local passwords. Airflow's login is
`AIRFLOW_ADMIN_USER` and `AIRFLOW_ADMIN_PASSWORD` from that file. Do not print
the resolved Compose configuration or commit `.env`.

## Batch pipeline and dashboard

```powershell
docker compose @base up -d --wait postgres
docker compose @base run --rm pipeline
docker compose @base --profile dashboard up -d --wait dashboard
```

Open <http://localhost:8501>. The batch command processes the full CSV dataset,
validates every stage, refreshes the local Olist database and warehouse, writes
reports, and publishes a complete Parquet snapshot. It intentionally replaces
the Olist tables in the configured database. Run it again for a fresh snapshot;
avoid running it concurrently with an Airflow refresh.

Container outputs live in the `olist_data` named volume, independently of the
host's `data/processed/` files. Each run is under `/opt/olist/data/runs/`.
`/opt/olist/data/processed/CURRENT.json` points to the most recently published
run. The dashboard, Spark exercise, and event producer follow that pointer.

## Airflow

```powershell
docker compose @stack up -d --wait airflow-apiserver airflow-scheduler airflow-dag-processor
docker compose @stack exec airflow-scheduler airflow dags list-import-errors
docker compose @stack exec airflow-scheduler airflow dags unpause ecommerce_pipeline
docker compose @stack exec airflow-scheduler airflow dags trigger ecommerce_pipeline
```

Open <http://localhost:8080> and inspect `ecommerce_pipeline`. The nine tasks are
ingest, validate_raw, clean, validate_clean, transform, validate_transformed,
load_database, analytics, and publish. The database task also refreshes the
warehouse. Each task retries twice with a two-minute delay. XCom carries run
paths; workers read shared storage.

The schedule defaults to manual, with catchup disabled and one active DAG run.
To schedule repeated refreshes, set `OLIST_SCHEDULE` in `.env` (for example
`@daily`), recreate the Airflow services, and unpause the DAG. This reprocesses
a static dataset; it does not partition historical inputs by logical date.

## Spark comparison

After publishing a batch snapshot:

```powershell
docker compose @base run --rm spark
```

This checks order joins, child aggregates, customer windows, and delivered
monthly totals against Pandas. Outputs and `reconciliation.csv` are in
`/opt/olist/data/processed/spark/`. `local[2]` uses two local Spark threads;
this is a learning exercise, not a distributed performance benchmark.

## Kafka event replay

After publishing a batch snapshot:

```powershell
docker compose @base --profile streaming up -d --wait kafka
docker compose @base run --rm kafka-init
docker compose @base run --rm producer
docker compose @base run --rm consumer python kafka/consumers/order_consumer.py --idle-timeout 15
```

The producer simulates lifecycle events from the first 1,000 source orders.
The topic has three partitions and uses order IDs as keys. The consumer writes
to `streaming.order_events`; malformed input goes to
`streaming.rejected_messages`. It commits Kafka offsets only after PostgreSQL
commits. Replaying deterministic event IDs does not create duplicate rows.
For a continuous consumer, use `docker compose @base up -d consumer`.

This single-broker local stack uses plaintext transport and is intended for
learning. Kafka events are simulated from historical CSVs, not live commerce
transactions, and do not update the batch warehouse or dashboard.

## Verification

```powershell
docker compose @base run --rm pipeline python -m unittest discover -s tests -v
docker compose @base run --rm pipeline python scripts/verify_services.py --with-kafka
docker compose @base run --rm -e OLIST_TEST_SPARK=1 spark python -m unittest tests.test_spark -v
docker compose @stack run --rm -e OLIST_TEST_AIRFLOW=1 airflow-scheduler python -m unittest tests.test_airflow -v
docker compose @stack run --rm airflow-scheduler python scripts/test_airflow_dag.py
```

Service verification uses the separate `olist_integration_test` database and
a temporary Kafka topic. The Airflow smoke run uses tiny fixture files in an
isolated data directory and disables its database stage. Trigger the actual
DAG as above to verify full-data orchestration with PostgreSQL.

The GitHub Actions workflow in `.github/workflows/` runs unit, Spark, database,
Kafka, and Airflow fixture checks without requiring the original CSV files.

## Inspect and stop

```powershell
docker compose @stack --profile dashboard --profile streaming ps
docker compose @stack logs --tail 100 airflow-scheduler airflow-dag-processor
docker compose @stack --profile dashboard --profile streaming down
```

`down` stops services while preserving named data volumes. Start the same
services again to resume. Keep `.env` so database credentials still match the
existing volumes. Containers expose PostgreSQL, Kafka, Airflow, and Streamlit
only on the host's loopback interface.
