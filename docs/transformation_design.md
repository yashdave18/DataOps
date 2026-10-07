# Phase 5 transformation design

The source is cleaned Parquet from phase 4. Reproduce all outputs with
`python -m src.transformation.transformations`, or run notebook 04. No database
is required. Input DataFrames are never mutated.

## Source grains and join contracts

| Source | One row | Key |
| --- | --- | --- |
| orders | Order | order_id |
| customers | Order-linked customer record | customer_id |
| order_items | Item/unit within an order | order_id, order_item_id |
| order_payments | Payment component within an order | order_id, payment_sequential |
| order_reviews | Latest retained review for an order | order_id |
| products | Catalog product | product_id |
| category translation | Portuguese category | product_category_name |

Keys must be unique and non-null. `customer_unique_id` may repeat in the
customer source; it identifies the person-level customer. It must not be null.
Joins declare `validate='many_to_one'` or `validate='one_to_one'`. Child order
IDs, order customer IDs, and item product IDs must resolve before aggregation.
Violations stop the transformation with a message for investigation; no orphan
rows are silently discarded. Category translations are optional matches.

## Orders

**One row = one order; key = `order_id`.** The orders table is the population
anchor, and every original order column, including cleaning flags, is retained.

1. Join customer attributes many-to-one on `customer_id`.
2. Join items to product categories many-to-one, then group by `order_id`.
3. Aggregate payments independently by `order_id`.
4. Join item/payment summaries and cleaned review attributes one-to-one.

| Features | Definition |
| --- | --- |
| total_item_value, total_freight | Sum of observed item price/freight |
| item_count, average_item_price | Number of item rows; mean observed price |
| product_count, seller_count, category_count | Distinct non-null identities/categories in the order |
| total_payment, payment_count | Sum of observed payment values; number of payment components |
| missing_item_price_count, missing_freight_count, missing_payment_value_count | Source-null amount counts, for interpreting incomplete sums |
| Payment flag columns | Any source payment has the cleaning flag; null when no payment exists |
| has_items, has_payments, has_review | Source child-row presence |
| review_score, has_comment | Latest review retained by phase 4; unknown for absent review |
| approval_delay_days | Approval minus purchase, fractional elapsed days |
| shipping_delay_days | Carrier handover minus approval, fractional elapsed days |
| delivery_duration_days | Customer delivery minus purchase, fractional elapsed days |
| carrier_delivery_days | Customer delivery minus carrier handover, fractional elapsed days |
| delivery_delay_days | Actual delivery calendar date minus estimated calendar date |
| is_late | Delivery delay > 0; null if either date is missing |
| purchase_year, purchase_month, purchase_day_of_week, purchase_hour | Local source timestamp components; month is YYYY-MM, weekday Monday=0 |
| payment_item_difference | Payment minus item value minus freight; diagnostic, not assumed zero |

Counts are zero for absent children, while monetary totals, means, review
scores, and child flags remain null. Negative durations are retained rather
than corrected. Estimated delivery is treated as a calendar date; delivery
later in the day on the expected date is on time. No timezone is inferred.

## Customers

**One row = one unique customer; key = `customer_unique_id`.** Start with all
distinct source customer identities, then left-join aggregated order features.
This retains one-time customers and customer identities with no orders.

Features include order count, observed payment spend, average known order
payment, item count, first/last purchase, elapsed active period, mean delivery
duration, mean review score, number of scored orders, number of orders with
payment rows, number with known payment totals, and repeat-customer indicator
(`order_count > 1`). Missing reviews do not become zero scores. For customers
with no orders, counts and spend are zero; dates and means are null. Customers
whose orders all lack payment values have unknown spend. Means exclude nulls;
`orders_with_known_payment` exposes the average-order-value denominator.

Preferred categories, cross-order distinct product/seller counts, and RFM
features are optional later extensions; they are not inferred from summed
order-level distinct counts.

## Products

**One row = one product; key = `product_id`.** Preserve the complete product
catalog, including dimensions, weight, photo counts, and cleaning flags.

1. Join category translations many-to-one with a left join; missing English
   names remain null and set `flag_missing_category_translation`.
2. Join items to analytical orders many-to-one to obtain unique customer IDs.
3. Aggregate item sales by product: units, distinct orders/customers/sellers,
   item revenue, freight, mean price/freight, and source-null amount counts.
4. Independently deduplicate product/order pairs, attach the order rating,
   and aggregate average review score and review count by product.
5. Join both summaries to the catalog one-to-one.

Repeated units of one product in an order contribute one rating. An order
containing several products contributes one rating to each product, so product
review counts are not additive across the catalog. Unsold products have zero
counts/revenue/freight and unknown averages/ratings.

## Assumptions and limitations

- All statuses are retained. Units sold and revenue describe recorded item
  rows, including canceled orders with items, not completed sales or net cash.
- Customer spend uses payments, while product revenue uses item prices.
  Neither refunds nor a net-revenue accounting model exist here.
- Sums skip individual null amounts but remain null for all-null groups.
  Missing-amount counts must be considered when using partial totals.
- The existing phase 4 latest-review selection is authoritative. Duplicate
  review orders are rejected rather than selected again during transformation.
- Reviews describe the whole order and cannot isolate a product or seller.
- Unknown product categories use the phase 4 `unknown` label; they count as a
  visible category. Missing translations do not remove products.
- Seller identities come from item rows; seller/geolocation enrichment is
  not required for these features. Known geographic coverage gaps remain
  documented in the cleaning decisions.
- These are retrospective features and include information unavailable at
  purchase time. Prediction tasks require a separate leakage review.

## Completion checks and outputs

`validate_analytical_datasets` enforces target uniqueness/non-null keys, exact
source-key populations, row counts, and monetary/count reconciliation before
export. Currency comparisons use `atol=0.01`, `rtol=0`; counts are exact.

Checks reconcile item value, freight and payments at order grain; spend,
orders, items and scored orders at customer grain; and revenue, freight,
units and distinct product/order pairs at product grain. The notebook also
displays null coverage, status coverage, distributions, negative intervals,
and payment-versus-item differences.

Outputs are `orders.parquet`, `customers.parquet`, `products.parquet`, and
`reconciliation.csv` under `data/processed/analytical/`. All Parquet files
are verified for exact values, dtypes and nulls before per-file replacement.
Original indices are deliberately not stored.

On the available dataset, all 20 checks pass: 99,441 orders, 96,096 unique
customers, 32,951 products, 112,650 item rows, and 103,886 payment rows.
Item value is 13,591,643.70 BRL, freight 2,251,909.54 BRL, and recorded payments
16,008,872.12 BRL. The phase 4 round trip was also verified for all nine tables
against freshly cleaned raw data, without rewriting raw or existing cleaned
files during verification.
