# Olist E-Commerce Dataset: EDA Summary

Summary of the 9 Olist tables, based on the notebook outputs (shape, dtypes, missing values, unique counts, duplicates, descriptive statistics).

## 1. Overview

| # | Dataset | Rows | Cols | Grain (one row per...) | Nulls | Full-row duplicates |
|---|---------|-----:|-----:|------------------------|-------|--------------------:|
| 1 | customers | 99,441 | 5 | order (`customer_id` is per order) | none | 0 |
| 2 | geolocation | 1,000,163 | 5 | coordinate sample (many per zip prefix) | none | **261,831** |
| 3 | order_items | 112,650 | 7 | item within an order | none | 0 |
| 4 | order_payments | 103,886 | 5 | payment within an order | none | 0 |
| 5 | order_reviews | 99,224 | 7 | review | title, message (optional text) | 0 |
| 6 | orders | 99,441 | 8 | order | 3 timestamp columns | 0 |
| 7 | products | 32,951 | 9 | product | category block (610), dimensions (2) | 0 |
| 8 | sellers | 3,095 | 4 | seller | none | 0 |
| 9 | category_translation | 71 | 2 | category | none | 0 |

## 2. Relationships and join keys

```
customers.customer_id  <->  orders.customer_id          (1:1)
orders.order_id        <->  order_items.order_id        (1:many)
orders.order_id        <->  order_payments.order_id     (1:many)
orders.order_id        <->  order_reviews.order_id      (1:many, a few duplicates)
order_items.product_id <->  products.product_id         (many:1)
order_items.seller_id  <->  sellers.seller_id           (many:1)
products.product_category_name <-> category_translation.product_category_name (many:1)
customers/sellers.zip_code_prefix <-> geolocation.zip_code_prefix (many:many, aggregate first)
```

Key points:

- `orders` is the hub table: one row per order, with unique `order_id` and `customer_id`. Left-join everything else onto it.
- `customer_id` is generated per order. `customer_unique_id` identifies the actual person (96,096 unique across 99,441 rows) and should be used for repeat-customer and retention analysis.
- Items, payments and reviews all have several rows per order. Aggregate to order level before joining, or rows will multiply.

## 3. Dataset details

### 3.1 customers (99,441 x 5)

- `customer_id` is unique (99,441). `customer_unique_id` has 96,096 unique values, so about 3,345 rows belong to repeat customers (one ID appears 17 times).
- 27 states. SP is dominant (41,746 rows, about 42.0%). Top city is `sao paulo` (15,540 rows, about 15.6%) out of 4,119 cities.
- `customer_zip_code_prefix` is `int64` with 14,994 unique values (min 1,003, max 99,990). Leading zeros are lost, e.g. `1151` should be `01151`.

### 3.2 geolocation (1,000,163 x 5)

- 261,831 fully duplicate rows (about 26%). Drop them.
- 19,015 unique zip prefixes over a million rows (about 52 points per prefix on average), so it is not one row per zip. Aggregate (mean or median lat/lng) to one row per prefix before joining.
- Coordinate outliers: lat ranges from -36.6 to +45.07 and lng from -101.47 to +121.1. Brazil sits roughly between lat 5.3 and -33.8 and lng -73.9 and -34.8, so some points are outside the country. Filter with a Brazil bounding box before mapping or distance work.
- 8,011 unique cities (against 4,119 in customers and 611 in sellers), which points to spelling variants, accents or typos. Normalise before matching on city.
- 27 states. SP has 404,268 rows (about 40.4%). `sao paulo` has 135,800 rows (about 13.6%).
- Zip prefix is `int64` (same leading-zero issue).

### 3.3 order_items (112,650 x 7)

- Natural key is (`order_id`, `order_item_id`). 98,666 unique orders (about 1.14 items per order), `order_item_id` max is 21 (mean 1.20).
- 32,951 products and 3,095 sellers. Top seller has 2,033 rows (about 1.8%), top product 527 rows, top order 21 rows.
- `shipping_limit_date` is a string (93,318 unique), so convert to datetime.

| Column | Mean | Std | Min | 25% | 50% | 75% | Max |
|--------|-----:|----:|----:|----:|----:|----:|----:|
| price | 120.65 | 183.63 | 0.85 | 39.90 | 74.99 | 134.90 | 6,735.00 |
| freight_value | 19.99 | 15.81 | 0.00 | 13.08 | 16.26 | 21.15 | 409.68 |

- Both are strongly right-skewed (mean well above median). Use medians or a log scale. Some items have zero freight.
- Item revenue is `price`. Order total is the sum of `price + freight_value` across items.

### 3.4 order_payments (103,886 x 5)

- 99,440 unique orders, so 1 order from `orders` has no payment record.
- `payment_sequential` goes up to 29 (mean 1.09), so some orders are paid in several parts (often a voucher plus another method). Sum `payment_value` per order for the total paid.
- 5 payment types. `credit_card` dominates (76,795 rows, about 73.9%). Check the rest for placeholders such as `not_defined`.
- `payment_installments`: min 0 (suspicious, a payment should have at least 1), median 1, mean 2.85, 75% 4, max 24.
- `payment_value`: min 0.00 (zero-value payments exist), median 100.00, mean 154.10, std 217.49, 25% 56.79, 75% 171.84, max 13,664.08 (right-skewed).
- 29,077 unique payment values.

### 3.5 order_reviews (99,224 x 7)

- Neither ID is unique: `review_id` has 98,410 unique values and `order_id` 98,673, with some appearing up to 3 times. Deduplicate per order (for example keep the latest `review_answer_timestamp`) before joining to orders.
- `review_score`: mean 4.09, std 1.35, median 5, 75th percentile also 5. Ratings skew heavily positive.
- `review_comment_title` is null in 87,656 rows (about 88.3%) and `review_comment_message` in 58,247 (about 58.7%). These are optional fields, so nulls mean "no comment". A `has_comment` flag is more useful than imputation.
- Comments are in Portuguese. Most common title is `Recomendo` (423), most common message is `Muito bom` (230).
- `review_creation_date` (636 unique) is date-only with every time at `00:00:00`. `review_answer_timestamp` has full times (98,248 unique). Both are strings, so convert to datetime.
- Coverage: 98,673 reviewed orders out of 99,441, so about 768 orders have no review.

### 3.6 orders (99,441 x 8)

- `order_id` and `customer_id` are both fully unique.
- `order_status` has 8 values. `delivered` is 96,478 (about 97.0%).
- Missing timestamps (mostly legitimate, from orders that never progressed):

| Column | Missing | Unique |
|--------|--------:|-------:|
| order_approved_at | 160 | 90,733 |
| order_delivered_carrier_date | 1,783 | 81,018 |
| order_delivered_customer_date | 2,965 | 95,664 |
| order_estimated_delivery_date | 0 | 459 |

- 96,478 orders are `delivered` but only 96,476 have a customer delivery date, so at least 2 delivered orders lack one. Cross-tab status against each null to find real anomalies.
- All 8 columns are strings. Convert the 5 timestamp columns with `pd.to_datetime`. `order_estimated_delivery_date` is date-only.

### 3.7 products (32,951 x 9)

- `product_id` is unique and matches the 32,951 distinct products in order_items.
- 610 products (about 1.9%) are missing category, name length, description length and photo count together. 2 products are missing weight and all three dimensions. Treat the 610 as "unknown category" rather than dropping them.
- Column typos in the source: `product_name_lenght`, `product_description_lenght`. Rename them.
- 73 categories. Largest is `cama_mesa_banho` (3,029 products, about 9.4%), followed by a long tail.

| Column | Mean | Min | 25% | 50% | 75% | Max |
|--------|-----:|----:|----:|----:|----:|----:|
| name length | 48.48 | 5 | 42 | 51 | 57 | 76 |
| description length | 771.50 | 4 | 339 | 595 | 972 | 3,992 |
| photos qty | 2.19 | 1 | 1 | 1 | 3 | 20 |
| weight (g) | 2,276.47 | 0 | 300 | 700 | 1,900 | 40,425 |
| length (cm) | 30.82 | 7 | 18 | 25 | 38 | 105 |
| height (cm) | 16.94 | 2 | 8 | 13 | 21 | 105 |
| width (cm) | 23.20 | 6 | 15 | 20 | 30 | 118 |

- Weight has a min of 0 g, which is not plausible, so check how many rows have zero weight. Weight is strongly right-skewed.
- Counts and measurements are floats only because of the NaNs.

### 3.8 sellers (3,095 x 4)

- `seller_id` is unique (3,095), matching the 3,095 sellers in order_items.
- 23 states (customers span 27). SP dominates with 1,849 sellers (about 59.7%). `sao paulo` has 694 sellers (about 22.4%) out of 611 cities.
- 2,246 unique zip prefixes (min 1,001, max 99,730), stored as `int64` (same leading-zero issue).
- Sellers are more concentrated in SP than customers are, which has implications for freight cost and delivery time.

### 3.9 product_category_name_translation (71 x 2)

- Maps Portuguese `product_category_name` to English `product_category_name_english`. 71 rows, all unique, no nulls, no duplicates.
- Products has 73 distinct categories but this table has 71 rows, so at least 2 categories in products have no translation. Check with an anti-join and add manual mappings.

## 4. Cross-table consistency checks

| Check | What the counts show |
|-------|----------------------|
| Orders with no items | 99,441 - 98,666 = about 775. Likely cancelled or unavailable, so verify against `order_status` |
| Orders with no payment | 99,441 - 99,440 = 1 |
| Orders with payments but no items | about 774 |
| Orders with no review | 99,441 - 98,673 = about 768 |
| Products in items vs products table | 32,951 vs 32,951, consistent |
| Sellers in items vs sellers table | 3,095 vs 3,095, consistent |
| Payments vs items per order | Sum of `payment_value` should roughly equal sum of `price + freight_value`. Differences come from vouchers, rounding and missing orders |

## 5. Data cleaning checklist

1. Drop the 261,831 duplicate rows in geolocation, filter to a Brazil bounding box, and aggregate to one row per zip prefix.
2. Zero-pad all zip prefixes to 5-character strings (customers, sellers, geolocation) before joining.
3. Convert all timestamp and date columns to datetime: `shipping_limit_date`, the 5 order timestamps, and both review dates.
4. Deduplicate reviews per `order_id` (keep the latest answer timestamp).
5. Aggregate items and payments to order level before joining to orders.
6. Fix the `lenght` column typos in products and handle the 610 products with missing category info.
7. Investigate `payment_installments = 0`, zero-value payments, and `product_weight_g = 0`.
8. Normalise city names (lowercase, accent-stripped, check variants) before matching on city.
9. Attach English category names via the translation table and handle the untranslated categories.
10. Check timestamp ordering in orders (purchase, approval, carrier, delivery) for inconsistent sequences.

## 6. Suggested analyses

- **Delivery performance:** delivery time, delay versus estimated date, approval lag and carrier handover lag, split by state and seller.
- **Reviews and delivery:** review score versus delivery delay, treating scores 1-2 as the unhappy-customer class.
- **Revenue and categories:** revenue by category (English names), month and state, and freight as a share of price.
- **Repeat customers:** retention using `customer_unique_id`.
- **Geography:** seller-to-customer distance from aggregated zip coordinates, and its relation to freight and delivery time.
- **Listing quality:** photo count, name length and description length against sales and review score.
- **Payments:** payment type and installment mix, and how it varies with order value.