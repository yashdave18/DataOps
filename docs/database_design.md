# PostgreSQL and warehouse design (phases 6–7)

The normalized `olist` schema stores all nine cleaned tables. The `warehouse`
schema is a separate analytical snapshot. Neither replaces the raw CSV or
processed Parquet layers.

## Relational contracts

`sql/schema/create_tables.sql` declares tables explicitly. Identifiers are
text, ZIP prefixes are five-character strings, source-local timestamps use
`timestamp without time zone`, and financial amounts use `numeric(18,2)`.
Physical dimensions retain nullable floating-point values. Flags use boolean.

Primary keys follow cleaned grains: orders, products, sellers, and
order-linked customers use their respective IDs; items use `(order_id,
order_item_id)`; payments use `(order_id, payment_sequential)`; reviews use
`order_id`. `review_id` is deliberately not unique. `customer_unique_id` is
indexed but not unique in the order-linked customer table.

Foreign keys enforce orders-to-customers, items-to-orders/products/sellers,
payments-to-orders, and reviews-to-orders. Important join/filter columns are
indexed. Nonnegative monetary and positive sequence constraints capture
defensible invariants. Zero installments, negative chronology, and other
flagged observations are retained rather than rejected.

ZIPs have no geography FK: some legitimate customer/seller ZIPs have no cleaned
coordinates. Category translation is a left-join lookup, with no mandatory FK,
so untranslated products remain visible. The loader does not drop records to
satisfy constraints.

## Loading and transaction behavior

`python -m src.database.loader` reads the nine Parquet files and loads them
with Psycopg `COPY`, naming columns explicitly. All tables load in one
transaction, in dependency order. Before commit, every persisted value/null
and the SQL order view are checked against Pandas; five SQL business reports
are also compared with independent Pandas calculations.

A populated target is rejected unless `--replace` is supplied. Replacement
deletes only the nine fixed `olist` tables in reverse dependency order; it
does not drop schemas, use `CASCADE`, or modify unrelated tables. Any failed
constraint, copy, or reconciliation rolls back the whole refresh. Concurrent
loads and warehouse refreshes use the same transaction advisory lock.

Use a dedicated application database. Connection settings come from
`DATABASE_URL`, or libpq's `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, and
`PGPASSWORD` variables/password file. `.env` is ignored by Git and not loaded
automatically by Python. Driver errors are logged without connection secrets.
The schema script supports repeated initialization, not migrations of an
arbitrary older schema; future schema changes require explicit migrations.

## Star schema

| Table | Grain | Key / role |
| --- | --- | --- |
| dim_customer | Unique person-level customer identity | Surrogate customer_key; unique customer_unique_id |
| dim_product | Catalog product | Surrogate product_key; category, physical features and cleaning flag |
| dim_seller | Seller | Surrogate seller_key; seller location |
| dim_geography | ZIP prefix | Surrogate geography_key; nullable representative coordinates |
| dim_date | Calendar date | YYYYMMDD date_key; role-playing date dimension |
| fact_orders | Order | Natural order_id; totals, counts, delivery and review measures |
| fact_order_items | Item/unit in an order | (order_id, order_item_id); additive price, freight and unit count |

The geography dimension uses the union of customer, seller, and geolocation
ZIPs. Uncovered ZIPs get a real dimension row with null geography attributes
and `has_coordinates=false`; no location is guessed. Customer geography is
attached to each order because a person can use different addresses. Seller
geography is attached to the seller dimension.

The date dimension spans all observed purchase, approval, carrier, delivery,
and estimated dates. Unknown dates remain nullable foreign keys. Surrogate
customer/product/seller/geography keys are snapshot-local: full refreshes may
reassign them. This is **type 1**, with no historical attribute tracking;
type 2 would require versioned records, effective dates, and stable key handling.

`python -m src.database.warehouse` rebuilds all seven warehouse tables in one
transaction and verifies nine population/money checks. It does not truncate
the source tables. A warehouse refresh is required after a cleaned-table
refresh. A failed refresh rolls back and preserves the previous warehouse.

Order payments and item totals live at order grain; item facts carry only
item measures. Do not sum order payments after joining orders to items.
Average review scores, delivery durations, and rates are non-additive.
An order can include multiple sellers/categories, so their order counts
cannot be added to obtain a global distinct-order count.

## SQL learning and validation

`sql/queries/` contains overview, monthly sales, category ranking, seller
performance, customer retention, and a business-query exercise bundle covering
SELECT/WHERE/CASE, HAVING, joins, CTEs, subqueries, conditional aggregates,
date functions, window ranking, lagged growth, and running totals.

Queries include all statuses unless stated otherwise. The order view sums
items and payments separately before joins. Category/product/seller ratings
deduplicate their order pairs before averaging. Cohort grids include only
observable months; future retention cells are absent, not zero.

`python -m src.database.validation` reruns the 15 database checks. It compares
null masks independently of Pandas' inferred SQL dtypes, then compares observed
values with `atol=1e-8`, `rtol=1e-12`. Currency is stored as exact SQL decimals.
Source amounts requiring silent rounding to cents fail validation.

Integration tests require `OLIST_TEST_DATABASE_URL` naming a dedicated database
ending in `_test`. Each test rolls back its outer transaction. Tests cover
foreign-key/duplicate rejection, rollback of failed replacement, intentional
reload, SQL/Pandas agreement, warehouse grains, missing translations/geography,
and repeated warehouse refreshes.

For isolated local verification with installed PostgreSQL binaries:

```powershell
.venv\Scripts\python.exe scripts/verify_postgres.py --bin-dir 'C:\path\to\pgsql\bin'
```

The helper creates a new authenticated cluster under ignored `.local/`, binds
only to a temporary localhost port, runs integration tests and the full dataset,
exports validation reports, and stops the server. It never installs a system
service or uses an existing database.

Implementation references: [Psycopg COPY](https://www.psycopg.org/psycopg3/docs/basic/copy.html),
[Psycopg transactions](https://www.psycopg.org/psycopg3/docs/basic/transactions.html),
[PostgreSQL constraints](https://www.postgresql.org/docs/17/ddl-constraints.html).
