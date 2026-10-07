# End-to-End Data Engineering and Data Science Project Plan

## 1. Project Goal

Build a complete data pipeline around the Olist Brazilian E-Commerce
dataset, starting from raw multi-table data and progressing through
ingestion, validation, cleaning, transformation, database design,
analytics, orchestration, scalable processing, streaming, dashboards,
and optional machine learning.

The main objective is not simply to produce an analysis. It is to learn
how real data moves through a system and how to write reusable, testable
code at each stage.

The project should preserve the raw data, make every transformation
reproducible, validate important assumptions, and maintain clear
separation between exploratory notebooks and reusable source code.

------------------------------------------------------------------------

## 2. Core Learning Objectives

By the end of the project, be comfortable with:

-   Python for data processing
-   Pandas and NumPy
-   Multi-table datasets
-   Data profiling and exploratory analysis
-   Data-quality validation
-   Missing values, duplicates, invalid values, and inconsistent
    categories
-   Datetime and categorical preprocessing
-   Data cleaning decisions
-   Table grain and cardinality
-   Joins and prevention of join explosions
-   GroupBy and aggregation
-   Feature engineering
-   Parquet
-   SQL
-   PostgreSQL
-   Relational modelling
-   Star schemas and analytical warehouses
-   ETL/ELT concepts
-   Pipeline testing
-   Airflow
-   Spark
-   Kafka
-   Docker
-   BI/dashboarding
-   Optional machine learning
-   Documentation and reproducibility

------------------------------------------------------------------------

## 3. Dataset

Use the Olist Brazilian E-Commerce dataset.

### Raw tables

1.  `olist_customers_dataset`
2.  `olist_geolocation_dataset`
3.  `olist_order_items_dataset`
4.  `olist_order_payments_dataset`
5.  `olist_order_reviews_dataset`
6.  `olist_orders_dataset`
7.  `olist_products_dataset`
8.  `olist_sellers_dataset`
9.  `product_category_name_translation`

Raw files belong in:

``` text
data/raw/
```

They must never be modified in place.

------------------------------------------------------------------------

## 4. Target Repository Structure

``` text
Data-analysis/
│
├── data/
│   ├── raw/
│   ├── interim/
│   ├── processed/
│   │   └── analytical/
│   └── external/
│
├── src/
│   ├── ingestion/
│   │   └── csv_ingestion.py
│   │
│   ├── validation/
│   │   └── data_quality.py
│   │
│   ├── cleaning/
│   │   ├── customers.py
│   │   ├── geolocation.py
│   │   ├── order_items.py
│   │   ├── payments.py
│   │   ├── order_reviews.py
│   │   ├── orders.py
│   │   ├── products.py
│   │   ├── sellers.py
│   │   └── category_translation.py
│   │
│   ├── transformation/
│   │   ├── order_features.py
│   │   ├── customer_features.py
│   │   └── product_features.py
│   │
│   ├── database/
│   ├── analytics/
│   └── utils/
│
├── notebooks/
│   ├── 01_data_exploration.ipynb
│   ├── 02_data_quality.ipynb
│   ├── 03_data_cleaning.ipynb
│   ├── 04_data_transformation.ipynb
│   └── 05_analytics.ipynb
│
├── sql/
│   ├── schema/
│   ├── queries/
│   └── warehouse/
│
├── tests/
│
├── airflow/
│   └── dags/
│
├── spark/
├── kafka/
│   ├── producers/
│   └── consumers/
│
├── dashboards/
├── docker/
├── docs/
│   ├── data_dictionary.md
│   ├── cleaning_decisions.md
│   ├── transformation_design.md
│   └── architecture.md
│
├── config/
├── logs/
│
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
└── plan.md
```

Not every later-stage directory needs implementation immediately. Build
the project phase by phase.

------------------------------------------------------------------------

# Phase 1 - Data Ingestion

## Objective

Create a reliable and reusable way to discover and load all raw CSV
datasets.

## Main file

``` text
src/ingestion/csv_ingestion.py
```

## Responsibilities

-   Locate `data/raw/` reliably.
-   Discover CSV files.
-   Load each CSV into a Pandas DataFrame.
-   Store DataFrames in a dictionary keyed by dataset name.
-   Detect missing expected datasets.
-   Handle important read failures.
-   Never transform or clean data during ingestion.

## Validation

Confirm:

-   All 9 expected datasets load.
-   Shapes are sensible.
-   Failed files are reported.
-   Missing datasets cause a clear failure.

## Status

Completed.

------------------------------------------------------------------------

# Phase 2 - Data Exploration

## Objective

Understand the dataset before modifying it.

## Main file

``` text
notebooks/01_data_exploration.ipynb
```

## Tasks

For every table investigate:

-   What does the table represent?
-   What does one row represent?
-   Shape
-   Column names
-   Data types
-   Example records
-   Missing values
-   Summary statistics
-   Unique-value counts
-   Duplicate rows
-   Candidate primary keys
-   Candidate foreign keys
-   Relationships to other tables
-   Suspicious values
-   Date fields
-   Numeric distributions
-   Categorical values

## Documentation

Maintain:

``` text
docs/data_dictionary.md
```

For each table record:

-   Dataset purpose
-   Row grain
-   Column meaning
-   Expected type
-   Candidate primary key
-   Foreign keys
-   Important observations

## Status

Completed.

------------------------------------------------------------------------

# Phase 3 - Data Quality Framework

## Objective

Build reusable validation functions independently of the Olist dataset.

## Main file

``` text
src/validation/data_quality.py
```

## Checks

The validation framework should support:

-   Missing values
-   Exact duplicates
-   Uniqueness
-   Expected data types
-   Numeric ranges
-   Categorical consistency
-   Date ordering
-   Outliers
-   Referential integrity

Each function should return structured findings rather than directly
cleaning data.

Suggested result schema:

``` text
table
check
column
count
percent
severity
message
```

## Application notebook

``` text
notebooks/02_data_quality.ipynb
```

This notebook:

-   Loads datasets.
-   Calls reusable validation functions.
-   Applies table-specific expectations.
-   Investigates findings.
-   Determines which findings are actual quality problems.

## Important principle

A validation warning is not automatically a cleaning instruction.

Examples:

-   Missing review text may be meaningful.
-   A high product price may be legitimate.
-   Multiple payments per order may be expected.
-   Referential gaps should not automatically cause deletion.

## Status

Completed.

------------------------------------------------------------------------

# Phase 4 - Data Cleaning

## Objective

Convert raw tables into trustworthy processed tables without inventing
unknown information or destroying legitimate observations.

## Main files

``` text
src/cleaning/
```

Cleaning should be table-specific.

## Principles

-   Never modify raw files.
-   Work on DataFrame copies.
-   Missing does not automatically mean invalid.
-   Outlier does not automatically mean erroneous.
-   Fix values only when the correction is defensible.
-   Flag uncertain anomalies rather than silently changing them.
-   Do not impute values merely to eliminate nulls.
-   Preserve important business information.
-   Document every material cleaning decision.

## Notebook

``` text
notebooks/03_data_cleaning.ipynb
```

Use it to:

-   Run cleaning functions.
-   Compare raw and cleaned shapes.
-   Compare null counts.
-   Compare data types.
-   Re-run quality checks.
-   Reconcile totals.
-   Inspect flags.
-   Verify important keys.
-   Confirm no accidental data loss.

## Output

``` text
data/processed/*.parquet
```

Use Parquet so that cleaned data types are preserved.

## Required final verification

Confirm the Parquet round trip preserves:

-   ZIP prefixes as strings including leading zeros
-   Datetime columns
-   Boolean/indicator flags
-   Null values
-   Numeric values

## Status

Completed. Exact values, nulls, and dtypes were verified for all nine
processed tables against freshly cleaned raw data. The round-trip check
is retained in notebook 03 and the reusable cleaning pipeline.

------------------------------------------------------------------------

# Phase 5 - Data Transformation and Analytical Datasets

## Objective

Transform cleaned relational tables into useful datasets at clearly
defined analytical grains.

This phase teaches table grain, joins, cardinality, aggregation, derived
features, temporal features, and reconciliation.

## Critical rule

Before every transformation, explicitly state:

``` text
ONE ROW = ?
```

Never join tables until their grains and relationship cardinalities are
understood.

------------------------------------------------------------------------

## 5.1 Order-Level Dataset

### File

``` text
src/transformation/order_features.py
```

### Target grain

``` text
ONE ROW = ONE ORDER
```

### Source tables to consider

-   orders
-   order_items
-   order_payments
-   order_reviews
-   customers
-   products where appropriate
-   sellers where appropriate

### Possible feature groups

Order identity:

-   order ID
-   customer ID
-   unique customer ID
-   order status

Financial:

-   total item value
-   total freight
-   total payment
-   item count
-   average item price

Composition:

-   number of products
-   number of sellers
-   number of categories

Time:

-   purchase timestamp
-   approval timestamp
-   carrier timestamp
-   delivery timestamp
-   estimated delivery timestamp
-   approval delay
-   shipping delay
-   delivery duration
-   delivery delay against estimate

Customer/review:

-   review score
-   comment indicator

Existing cleaning flags should be preserved when useful.

### Core learning problem

Avoid join multiplication.

If an order contains:

``` text
2 item rows
3 payment rows
```

joining both raw child tables directly can produce:

``` text
2 x 3 = 6 rows
```

and duplicate monetary values.

Aggregate child tables to the required grain before joining.

### Validation

Check:

-   `order_id` is unique.
-   Row count equals expected order count.
-   Item totals reconcile with cleaned order-items.
-   Freight totals reconcile.
-   Payment totals reconcile.
-   Review joins do not multiply orders.
-   No unexpected order IDs disappear.
-   Join-created nulls are understood.

------------------------------------------------------------------------

## 5.2 Customer-Level Dataset

### File

``` text
src/transformation/customer_features.py
```

### Target grain

``` text
ONE ROW = ONE UNIQUE CUSTOMER
```

Use the appropriate customer identity rather than assuming `customer_id`
represents a person.

### Possible features

-   number of orders
-   total spend
-   average order value
-   total items purchased
-   first purchase
-   last purchase
-   active period
-   average delivery duration
-   average review score
-   number of reviewed orders
-   preferred categories
-   number of distinct products
-   number of distinct sellers
-   repeat-customer indicator

Potential later analytical features:

-   recency
-   frequency
-   monetary value

### Validation

Check:

-   Customer key is unique.
-   Aggregated order count reconciles.
-   Total spend reconciles with order-level data.
-   No unexpected customers disappear.
-   One-time customers are retained.
-   Null review values are not interpreted as zero ratings.

------------------------------------------------------------------------

## 5.3 Product-Level Dataset

### File

``` text
src/transformation/product_features.py
```

### Target grain

``` text
ONE ROW = ONE PRODUCT
```

### Possible features

-   product ID
-   category
-   English category
-   units sold
-   number of orders
-   number of customers
-   revenue
-   average selling price
-   average freight
-   average review score
-   review count
-   seller count
-   physical dimensions
-   weight
-   photo count

### Validation

Check:

-   `product_id` is unique.
-   Product revenue reconciles with order-item totals.
-   Units sold reconcile.
-   Products with no translation remain visible.
-   Review joins do not duplicate item revenue.

------------------------------------------------------------------------

## 5.4 Transformation Notebook

### File

``` text
notebooks/04_data_transformation.ipynb
```

The notebook is for applying and validating reusable transformation
code.

Investigate:

-   Before/after shapes
-   Uniqueness
-   Join cardinality
-   Nulls introduced by joins
-   Aggregate reconciliation
-   Distribution of engineered features
-   Suspicious transformed values

Do not hide transformation logic only inside the notebook.

------------------------------------------------------------------------

## 5.5 Transformation Documentation

Create:

``` text
docs/transformation_design.md
```

Document each analytical dataset:

-   Grain
-   Primary key
-   Source tables
-   Join path
-   Cardinality
-   Aggregations
-   Derived columns
-   Important assumptions
-   Known limitations
-   Reconciliation checks

------------------------------------------------------------------------

## 5.6 Outputs

``` text
data/processed/analytical/orders.parquet
data/processed/analytical/customers.parquet
data/processed/analytical/products.parquet
```

### Phase completion criteria

Do not move forward until:

-   All three grains are explicit.
-   Keys are unique.
-   Financial totals reconcile.
-   Join multiplication has been ruled out.
-   Transformation logic is reusable.
-   Outputs can be regenerated from processed data.

------------------------------------------------------------------------

## Phase 5 Status

Completed. Order, unique-customer, and product outputs are implemented,
validated, and exported. All 20 reconciliation checks pass on the full
dataset. See `docs/transformation_design.md` and notebook 04.

------------------------------------------------------------------------

# Phase 6 - PostgreSQL and SQL

## Objective

Move beyond Pandas and learn to store, query, join, and aggregate data
in a relational database.

## Tasks

### 6.1 Database schema

Create SQL under:

``` text
sql/schema/
```

Design tables for cleaned datasets.

Learn:

-   Primary keys
-   Foreign keys
-   Data types
-   Constraints
-   Indexes
-   Normalization
-   Referential integrity

### 6.2 Python database loading

Use:

``` text
src/database/
```

Responsibilities:

-   Establish database connection.
-   Load processed datasets.
-   Create/replace tables intentionally.
-   Handle transactions.
-   Log failures.

Credentials belong in environment variables, never source code.

### 6.3 SQL practice

Store reusable queries in:

``` text
sql/queries/
```

Cover:

-   SELECT
-   WHERE
-   CASE
-   GROUP BY
-   HAVING
-   INNER JOIN
-   LEFT JOIN
-   CTEs
-   Subqueries
-   Window functions
-   Ranking
-   Running totals
-   Date functions
-   Conditional aggregation

### Business questions

Examples:

-   Monthly revenue
-   Average order value
-   Repeat-customer rate
-   Top categories
-   Seller performance
-   Delivery performance
-   Customer retention
-   Review-score relationships
-   Freight as a percentage of order value

### Validation

Compare important SQL results against Pandas calculations.

------------------------------------------------------------------------

## Phase 6 Status

Completed. Nine explicit PostgreSQL tables, transactional COPY loading,
intentional replacement, SQL business queries, and 15 SQL/Pandas checks
are implemented and verified on the full dataset with PostgreSQL 17.11.

------------------------------------------------------------------------

# Phase 7 - Data Warehouse / Star Schema

## Objective

Learn the difference between normalized operational tables and
analytics-oriented warehouse models.

## Directory

``` text
sql/warehouse/
```

## Design

Create a star schema based on the business process.

Possible structure:

``` text
fact_order_items
fact_orders / fact_payments if justified

dim_customer
dim_product
dim_seller
dim_date
dim_geography
```

The exact design should be justified rather than copied mechanically.

## Learn

-   Facts
-   Dimensions
-   Measures
-   Surrogate keys
-   Natural keys
-   Grain
-   Slowly changing dimensions conceptually
-   Denormalization
-   Analytical query performance

## Validation

Every fact table must have an explicitly documented grain.

------------------------------------------------------------------------

## Phase 7 Status

Completed. Five dimensions and two fact tables have explicit grains,
transactional snapshot refreshes, and nine successful reconciliation checks.
The type 1 model and missing-geography policy are documented.

------------------------------------------------------------------------

# Phase 8 - Analytics and EDA

## Objective

Use the processed/analytical data to answer business questions.

## Files

``` text
src/analytics/
notebooks/05_analytics.ipynb
```

Reusable analytical calculations should go into `src/analytics/`;
exploration and presentation can occur in the notebook.

## Areas

### Sales

-   Revenue over time
-   Order growth
-   Average order value
-   Category performance
-   Seasonality

### Customers

-   New vs repeat customers
-   Purchase frequency
-   Customer spend distribution
-   Retention/cohorts
-   RFM-style analysis

### Products

-   Best-selling products
-   Revenue by category
-   Price distribution
-   Product review performance

### Logistics

-   Delivery time
-   Late-delivery rate
-   Freight cost
-   Seller/location effects

### Reviews

-   Score distribution
-   Relationship between delivery delay and score
-   Comment behaviour
-   Product/category satisfaction

## Visualization

Use visualizations to answer specific questions, not simply because a
chart can be created.

------------------------------------------------------------------------

## Phase 8 Status

Completed. Shared analytics cover sales, customers/cohorts/RFM, products,
sellers, geography, logistics, and reviews. Notebook 05 and CSV reports
use the reusable calculations and document populations and denominators.

------------------------------------------------------------------------

# Phase 9 - Dashboard

## Objective

Present useful metrics interactively.

## Directory

``` text
dashboards/
```

Power BI is appropriate for this project.

## Possible pages

### Executive overview

-   Revenue
-   Orders
-   Customers
-   Average order value
-   Review score

### Sales

-   Revenue trends
-   Categories
-   Products

### Customers

-   Repeat rate
-   Geographic distribution
-   Cohorts

### Logistics

-   Delivery performance
-   Freight
-   Delayed orders

### Reviews

-   Ratings
-   Delivery vs satisfaction

Connect the dashboard to PostgreSQL or curated analytical exports.

------------------------------------------------------------------------

## Phase 9 Status

Completed with a runnable Streamlit dashboard using curated Parquet.
Five views share status/date filters and CSV downloads. Navigation and
empty selections are tested. CSV exports also support Power BI; no PBIX
file is generated.

------------------------------------------------------------------------

# Phase 10 - Testing

Testing should gradually be added throughout the project rather than
postponed entirely until the end.

## Directory

``` text
tests/
```

## Test categories

### Ingestion

-   Missing directory
-   Missing dataset
-   Malformed CSV
-   Successful loading

### Validation

-   Missing-value detection
-   Duplicate detection
-   Unique-key detection
-   Range checks
-   Date ordering
-   Referential integrity

### Cleaning

-   Raw input is not mutated.
-   ZIP formatting works.
-   Datetimes convert correctly.
-   Flags are created correctly.
-   Expected row counts are preserved/dropped.

### Transformation

-   Expected grain is unique.
-   Aggregates reconcile.
-   Joins do not multiply rows.
-   Required columns exist.

### Database

-   Tables load.
-   Keys/constraints behave correctly.

Focus on meaningful tests rather than maximizing test count.

------------------------------------------------------------------------

# Phase 11 - Pipeline Orchestration with Airflow

## Objective

Turn individually runnable stages into an orchestrated pipeline.

## Directory

``` text
airflow/dags/
```

## Example dependency flow

``` text
ingest
   ↓
validate_raw
   ↓
clean
   ↓
validate_clean
   ↓
transform
   ↓
validate_transformed
   ↓
load_database
   ↓
refresh_analytics
```

## Learn

-   DAGs
-   Tasks
-   Dependencies
-   Scheduling
-   Retries
-   Idempotency
-   Logging
-   Failure handling
-   Backfills conceptually

The DAG should call reusable source code rather than duplicating
notebook code.

------------------------------------------------------------------------

# Phase 12 - Spark

## Objective

Learn distributed data processing after understanding the same
operations in Pandas.

## Directory

``` text
spark/
```

Reimplement selected operations such as:

-   Reading Parquet
-   Filtering
-   Grouping
-   Joining
-   Aggregation
-   Window functions

Compare Spark and Pandas:

-   API
-   Execution model
-   Lazy evaluation
-   Partitioning
-   Shuffles
-   Performance tradeoffs

The Olist dataset does not require Spark for scale. Spark is included as
a learning exercise.

------------------------------------------------------------------------

# Phase 13 - Kafka / Streaming

## Objective

Understand event-driven data pipelines.

## Directories

``` text
kafka/producers/
kafka/consumers/
```

Simulate events such as:

``` json
{
  "order_id": "...",
  "customer_id": "...",
  "event_type": "order_created",
  "timestamp": "..."
}
```

Potential events:

-   Order created
-   Payment completed
-   Order shipped
-   Order delivered
-   Review submitted

## Learn

-   Producer
-   Consumer
-   Topic
-   Partition
-   Offset
-   Consumer group
-   Event schema
-   At-least-once processing
-   Idempotency

A consumer can aggregate or persist events into a database.

------------------------------------------------------------------------

# Phase 14 - Docker

## Objective

Make the project reproducible across machines.

## Directory

``` text
docker/
```

Containerize appropriate services:

-   Application/Python environment
-   PostgreSQL
-   Airflow
-   Kafka if retained

Use Docker Compose where useful.

## Learn

-   Images
-   Containers
-   Volumes
-   Networks
-   Environment variables
-   Service dependencies

------------------------------------------------------------------------

# Phase 15 - Optional Cloud Deployment

Only after the local pipeline works.

Possible learning goals:

-   Object storage for raw/processed data
-   Managed PostgreSQL
-   Scheduled pipeline execution
-   Container deployment
-   Secret management
-   Logging/monitoring

Do not add cloud complexity before the local architecture is reliable.

------------------------------------------------------------------------

# Phase 16 - Optional Machine Learning

Machine learning is deliberately late in this project.

The dataset should first become trustworthy and analysis-ready.

Potential problems:

### Review-score prediction

Predict review satisfaction using:

-   Delivery performance
-   Freight
-   Product/category
-   Order characteristics

### Delivery-delay prediction

Predict whether an order will arrive after its estimated delivery date.

### Customer segmentation

Use customer-level behavioural features.

## ML workflow

``` text
problem definition
→ target definition
→ leakage analysis
→ train/validation/test split
→ preprocessing
→ baseline
→ feature engineering
→ model
→ evaluation
→ error analysis
```

Avoid using future information unavailable at prediction time.

------------------------------------------------------------------------

# Phase 17 - Documentation and Finalization

## README

The final `README.md` should explain:

-   Problem
-   Dataset
-   Architecture
-   Repository structure
-   Setup
-   Pipeline
-   Data-quality findings
-   Cleaning decisions
-   Analytical datasets
-   Database/warehouse
-   Dashboard
-   Technologies
-   Major insights
-   Limitations
-   How to reproduce

## Architecture document

Create:

``` text
docs/architecture.md
```

Final conceptual architecture:

``` text
Raw CSV / API / Events
        ↓
Ingestion
        ↓
Raw Validation
        ↓
Cleaning
        ↓
Clean Validation
        ↓
Processed Parquet
        ↓
Transformation
        ↓
Analytical Datasets
        ↓
PostgreSQL / Warehouse
        ↓
SQL Analytics
        ↓
Dashboard / ML

Orchestration: Airflow
Scale learning: Spark
Streaming learning: Kafka
Environment: Docker
```

------------------------------------------------------------------------

# Development Rules

## 1. Notebooks vs source code

Use notebooks for:

-   Investigation
-   Exploration
-   Visualization
-   Validation
-   Comparing alternatives

Use `src/` for:

-   Reusable functions
-   Cleaning logic
-   Transformation logic
-   Database logic
-   Production-style analytics

If logic is needed repeatedly, it should probably leave the notebook.

## 2. Preserve raw data

Never overwrite:

``` text
data/raw/
```

## 3. Every table has a grain

Before manipulating a table, be able to finish:

> One row represents ...

## 4. Validate joins

Before joining, determine whether the relationship is:

-   one-to-one
-   one-to-many
-   many-to-one
-   many-to-many

After joining, check row counts and key uniqueness.

## 5. Reconcile important measures

After transformations, compare:

-   Revenue
-   Payments
-   Freight
-   Item counts
-   Order counts
-   Customer counts

against their source tables.

## 6. Do not silently fix uncertain data

Prefer:

``` text
investigate → document → flag → account for in analysis
```

over:

``` text
guess → overwrite
```

## 7. Keep commits phase-oriented

Example commit history:

``` text
Add CSV ingestion pipeline
Add exploratory data analysis
Add reusable data quality checks
Add data quality investigation
Add table cleaning pipeline
Add cleaning validation and processed outputs
Add order-level transformations
Add customer and product analytical datasets
Add PostgreSQL schema and loading
Add SQL analytics
Add warehouse model
Add Airflow orchestration
```

------------------------------------------------------------------------

# Project Milestones

  Milestone   Deliverable                           Status
  ----------- ------------------------------------- -------------
  M1          Repository structure                  Done
  M2          Raw ingestion                         Done
  M3          Initial exploration/data dictionary   Done
  M4          Reusable quality framework            Done
  M5          Quality investigation                 Done
  M6          Cleaning pipeline                     Done
  M7          Processed Parquet verification        Done
  M8          Order analytical dataset              Done
  M9          Customer analytical dataset           Done
  M10         Product analytical dataset            Done
  M11         PostgreSQL + SQL                      Done
  M12         Warehouse model                       Done
  M13         Analytics/EDA                         Done
  M14         Dashboard                             Done
  M15         Tests expanded                        Done
  M16         Airflow pipeline                      Done
  M17         Spark exercise                        Done
  M18         Kafka exercise                        Done
  M19         Dockerized stack                      Done
  M20         Optional cloud/ML                     Deferred
  M21         Final README and architecture         Done

------------------------------------------------------------------------

# Immediate Next Tasks

Phases 1-14 and phase 17 are implemented. Docker Desktop now runs the local
PostgreSQL, Kafka, Airflow, and dashboard services. The batch runner preserves
source hashes, applies quality gates, refreshes the database and warehouse
transactionally, and publishes complete snapshots through an atomic pointer.

Expanded tests include real PostgreSQL rollback checks, Kafka replay and
offset checks, Spark/Pandas comparisons, and execution of the actual Airflow
DAG. GitHub Actions reproduces the fixture checks without the original CSVs.

Use `docs/local_stack.md` for build, batch refresh, DAG triggering, Spark,
event replay, verification, and shutdown commands. See `docs/architecture.md`
for transaction boundaries, retry behavior, and local-stack limitations.

Optional cloud deployment and machine learning remain deliberately deferred.
They are separate extensions after this verified local learning stack.

------------------------------------------------------------------------

# Definition of Project Completion

The project is complete when another person can clone the repository,
follow the setup instructions, reproduce the pipeline, and understand:

1.  Where the data came from.
2.  What every important table represents.
3.  What quality problems existed.
4.  Why each cleaning decision was made.
5.  How cleaned data becomes analytical data.
6.  How joins and aggregates were validated.
7.  How data is stored and queried.
8.  How the pipeline is orchestrated.
9.  What business insights were produced.
10. What limitations remain.

The final project should demonstrate not merely that data was analyzed,
but that it was handled correctly from ingestion to consumption.
