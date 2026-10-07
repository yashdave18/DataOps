# Local verification: 7 October 2026

Verified on Windows with Docker Desktop's Linux engine. Commands for repeating
these checks are in [the local stack runbook](local_stack.md). These results
describe this verification session, not continuous monitoring or hosted CI.

## Automated checks

| Check | Result |
| --- | --- |
| Application image: unittest discovery | 48 discovered; 39 passed, 9 explicitly deferred to service runs |
| PostgreSQL and Kafka integration | 7 passed, including warehouse-failure rollback, event replay, malformed-message quarantine, and committed offsets |
| Spark fixture comparison | 1 passed, including multiple child rows and missing payments |
| Airflow DAG structure and retries | 1 passed |
| Actual Airflow fixture execution | All nine tasks succeeded and published an isolated snapshot |
| Dashboard with full dataset | Overview, Sales, Customers, Logistics, and Reviews rendered without app errors |

All 48 discovered tests were exercised across these runtime-specific runs.
The GitHub Actions workflow is configured; no remote Actions run is claimed.

## Full dataset and services

The standalone container run `20261007T085936-1257861a` completed all nine
pipeline stages, including database reconciliation and warehouse refresh.

The scheduler-driven Airflow run `docker-verification-20261007` also succeeded
on the full dataset, with all nine tasks succeeding on their first attempt.
It ran from 14:34:01 to 14:41:15 IST and published
`airflow-e99e1e6ad396dde28bb6c9c1` as the current snapshot. This exercised the
LocalExecutor and execution API as well as the real PostgreSQL load.

| Output | Verified rows |
| --- | ---: |
| Analytical orders | 99,441 |
| Analytical unique customers | 96,096 |
| Analytical products | 32,951 |
| PostgreSQL orders | 99,441 |
| Warehouse order fact | 99,441 |
| Warehouse order-item fact | 112,650 |
| Kafka events persisted from 1,000 source orders | 4,812 |

Spark matched all 99,441 order rows and 23 delivered purchase-month rows
against Pandas, including customer windows and cumulative monthly totals.
The event consumer reported 4,812 inserted, zero duplicates, and zero rejected
for the initial full replay. Duplicate and invalid input were separately
verified by the integration test.

## Corrections made during verification

- The pipeline now opens an explicit outer database transaction around the
  cleaned-table load and warehouse refresh. A forced warehouse failure test
  confirms that the previous cleaned data survives.
- Kafka now advertises `127.0.0.1:9092` to host clients, matching the IPv4
  loopback port binding. The previous `localhost` address resolved to IPv6
  first on this Windows machine and failed the host integration check.

The local `.env` was preserved. Raw CSVs were mounted read-only. Container
outputs use named volumes, and service tests use a separate test database.
Cloud deployment and machine learning were not part of this verification.
