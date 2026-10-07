# Implemented local architecture

```text
data/raw/*.csv (immutable)
    -> src.ingestion.csv_ingestion
    -> quality investigation (notebooks 01–02, src.validation)
    -> src.cleaning.pipeline (table-specific cleaning functions)
    -> data/processed/*.parquet (exact round-trip verification)
    -> src.transformation.transformations
       -> order features (child aggregates before joins)
       -> unique customer features (from analytical orders)
       -> product features (separate sales and review aggregates)
    -> key, population, money, and count reconciliation
    -> data/processed/analytical/*.parquet + reconciliation.csv
       -> src.analytics.metrics / reports -> CSV reports + notebook 05
       -> dashboards/app.py (Streamlit, shared metric definitions)

data/processed/*.parquet
    -> src.database.loader (transactional COPY + complete SQL/Pandas checks)
    -> PostgreSQL olist schema (nine tables + order_metrics view)
    -> src.database.warehouse (transactional type 1 snapshot refresh)
    -> PostgreSQL warehouse schema (five dimensions + two facts)
    -> reusable SQL business queries / external BI
```

Notebooks investigate and display results; reusable source modules implement
the pipeline. Cleaning preserves the existing documented decisions. Output
files omit the pandas index. Each file is written to a temporary sibling,
read back, checked for exact values/nulls/dtypes, and then replaces its target.
This is atomic per file, not a transaction over the entire output directory.

The transformation stage fails on invalid primary keys, unexpected duplicate
review orders, or orphan relationships used in its joins. It never resolves
such findings by deleting rows. Missing category translations are allowed
and flagged. Geographic enrichment is not needed for the current features;
the known ZIP coverage gaps therefore do not exclude orders or customers.

PostgreSQL load/warehouse validation complements the existing Pandas/Parquet
checks. The database and file outputs are separate snapshots; refresh both
after changing cleaned inputs. The dashboard deliberately uses the curated
files so interactive exploration does not require a running server. Its
status/date filters affect all calculations, and unknown outcomes remain
excluded from rate denominators.

## Orchestrated snapshots

`src.pipeline.runner` adds nine sequential stages around the reusable modules.
Ingestion records SHA-256 source hashes and snapshots raw tables under
`data/runs/<run_id>/raw_snapshot/`. Quality gates stop invalid runs before
publication. Each run has separate processed files, reports, configuration,
and stage completion records. Retrying a published run does not modify it or
republish an older snapshot. Retrying ingestion with changed sources fails.

After every stage succeeds, publication atomically replaces
`data/processed/CURRENT.json`. File consumers resolve this pointer to a complete
run. The original standalone module commands still write per-file outputs;
use the runner or Airflow for complete snapshot publication.

When database loading is enabled, cleaned tables and the warehouse refresh
share one PostgreSQL transaction. Database commit and file publication are
separate operations: a later analytics failure can leave PostgreSQL ahead of
the dashboard's last published snapshot. Run only one database-writing batch
at a time; Airflow enforces this for its own DAG, but not for standalone CLI
runs started alongside it.

Airflow uses LocalExecutor, a separate metadata database, an API server, a
scheduler, and a DAG processor. The DAG invokes the same stages, carries only
paths through XCom, retries failures, and disables catchup. Scheduling defaults
to manual because the input is a static historical dataset.

## Spark and streaming

The Spark exercise reads the published Parquet snapshot, aggregates children
before joining orders, applies customer and monthly windows, and compares
results with Pandas. It runs locally with two threads and collects this small
dataset to the driver. It demonstrates lazy execution and shuffle operations;
it is not a cluster deployment or a controlled speed benchmark.

The Kafka producer simulates deterministic lifecycle events from cleaned
orders and reviews. A three-partition topic keys events by order ID. The
consumer validates messages, persists accepted events or rejected payloads
in PostgreSQL's separate `streaming` schema, then synchronously commits
offsets. Unique event IDs deduplicate replay after a crash between database
commit and offset acknowledgement. This is at-least-once delivery with an
idempotent sink. Streaming is independent of the batch analytical tables.

## Containers and verification

Docker Compose supplies PostgreSQL plus optional batch, dashboard, Spark,
and Kafka services; the Airflow overlay supplies orchestration. A shared named
volume holds run snapshots and read-only bind mounts expose original CSVs.
Application and Airflow processes use UID 50000 so they can share outputs.
Database, Kafka, and Airflow metadata/log volumes persist across restarts.
Host ports bind to loopback. Secrets come from an ignored, generated `.env`.

Tests cover quality failures, retry behavior, snapshot publication, SQL and
warehouse transactions, event rejection/deduplication, real Kafka offsets,
Spark/Pandas equivalence, and actual Airflow fixture execution. CI starts
disposable local services and needs no original Olist data. Optional cloud
deployment and machine learning remain deferred.

See [the local stack runbook](local_stack.md) for startup, verification,
manual DAG triggering, streaming replay, and shutdown commands.

See `database_design.md` for dimensional grains, transaction behavior, and
SQL validation; see `../dashboards/README.md` for interactive use.
