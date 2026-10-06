# Cleaning Decisions

How `data/raw/` becomes `data/processed/`. Raw tables are never modified: every cleaning function works on a copy, and cleaned tables are written to `data/processed/` as parquet (parquet keeps the fixed types, which CSV would lose).

## Principles

- Missing is not automatically bad. A null can carry meaning (no comment, order never shipped).
- An outlier is not automatically bad. Investigate before acting.
- Fix a value only when the correct value is known with certainty.
- Prefer flagging over deleting when unsure, so information is preserved.
- Drop only exact duplicates, impossible rows, or rows whose removal leaves no other table with orphans.

Action key: **Fix** (change the value), **Flag** (add an indicator column, keep the data), **Leave** (no change), **Drop** (remove rows).

## Pipeline

```
data/raw/  ->  load_datasets()  ->  quality checks  ->  cleaning functions (on copies)
           ->  re-validation  ->  data/processed/*.parquet  ->  raw vs cleaned comparison
```

| Table | Cleaning function | Rows raw -> cleaned |
|---|---|---|
| customers | `src/cleaning/customers.py` `clean_customers` | 99,441 -> 99,441 |
| geolocation | `src/cleaning/geolocation.py` `clean_geolocation` | 1,000,163 -> 19,010 |
| order_items | `src/cleaning/order_items.py` `clean_order_items` | 112,650 -> 112,650 |
| order_payments | `src/cleaning/payments.py` `clean_payments` | 103,886 -> 103,886 |
| order_reviews | `src/cleaning/order_reviews.py` `clean_order_reviews` | 99,224 -> 98,673 |
| orders | `src/cleaning/orders.py` `clean_orders` | 99,441 -> 99,441 |
| products | `src/cleaning/products.py` `clean_products` | 32,951 -> 32,951 |
| sellers | `src/cleaning/sellers.py` `clean_sellers` | 3,095 -> 3,095 |
| category translation | `src/cleaning/category_translation.py` `clean_category_translation` | 71 -> 74 |

---

## customers

| Issue | Evidence | Action | Why |
|---|---|---|---|
| `customer_zip_code_prefix` stored as `int64`, leading zeros lost | min 1,003; `1151` should be `01151` | **Fix**: convert to text, pad to 5 characters | The correct value is certain, and it must match the other zip columns when joining |
| `customer_id` is per order, `customer_unique_id` has 96,096 distinct values | EDA | **Leave** | Repeat customers are real. Use `customer_unique_id` for retention analysis |
| City and state spelling | quality check found no variants | **Leave** | Nothing to fix |
| 278 customer rows have a zip prefix with no geolocation record (279 after geolocation cleaning) | referential integrity check | **Leave** | Coordinates cannot be invented. Known limitation for distance analysis |

Verified: 14,994 distinct zips before and after, all values length 5, converting back to integers matches raw exactly, all other columns identical.

## geolocation

| Issue | Evidence | Action | Why |
|---|---|---|---|
| 261,831 exact duplicate rows | `duplicated()` | **Drop** | Identical copies carry no information |
| Zip prefix stored as `int64` | EDA | **Fix**: 5-character text | Same as customers and sellers |
| City names with several spellings (2,037 names, 484,585 rows involved) | categorical check | **Fix**: lowercase, trim, remove accents | Variants of one city should match |
| 47 rows with coordinates outside Brazil (23 prefixes) | bounding box lat -33.8 to 5.3, lng -73.9 to -34.8 | **Drop** | State and city were Brazilian but coordinates were not (for example Texas, Buenos Aires): geocoding matched same-named places abroad |
| About 52 coordinate rows per prefix | 19,015 prefixes over 1M rows | **Fix**: aggregate to one row per prefix (median lat/lng, most common city and state) | A join to customers or sellers would otherwise multiply rows |

Consequences:

- 5 prefixes had only out-of-Brazil points and are absent from the cleaned table: `18243`, `53990`, `78131`, `83252`, `95130`. That is why unmatched customer zips went from 278 to 279. Unmatched seller zips stayed at 7.
- The bounding box is a rectangle around Brazil. It removes coordinates in other countries but cannot catch a wrong point that falls inside the rectangle. Taking the median per prefix softens that effect.

## order_items

| Issue | Evidence | Action | Why |
|---|---|---|---|
| `shipping_limit_date` stored as text | EDA | **Fix**: convert to datetime | Needed for date arithmetic. No nulls introduced |
| 383 rows with `freight_value` = 0 | 369 of 383 (96%) come from 4 sellers, normal prices (median 99.90), every item in the multi-item sample orders had 0 freight | **Leave** | Consistent with seller free-shipping policy, so the 0 is meaningful |
| Price and freight flagged as IQR outliers (8,427 and 12,134 rows) | right-skewed distributions | **Leave** | Skew is normal for prices. Nothing indicates errors |

Verified: key (`order_id`, `order_item_id`) still unique, no nulls, price and freight sums identical to raw.

## order_payments

| Issue | Evidence | Action | Why |
|---|---|---|---|
| 2 `credit_card` rows with `payment_installments` = 0 | values 58.69 and 129.94. Both are payment row 2 and the only payment row of their order | **Flag** (`flag_zero_installments`), keep the value | The table's usual value for a single payment is 1, so 0 is unusual. Its true meaning is unknown, so changing it would invent data |
| 9 rows with `payment_value` = 0 | 6 voucher rows (parts 3, 4, 13, 14), 3 `not_defined` rows | **Leave** | Zero-value voucher parts are plausible. All 3 `not_defined` rows (the whole category) belong to canceled orders, where no payment method was chosen |
| 80 orders (82 rows) have no payment row numbered 1 | 78 orders with one row, 2 orders with two rows. No gaps in the middle | **Flag** (`flag_missing_first_payment`), no row invented | The missing amount is unknown. Totals summed per order may be too low for these orders |
| Several payment rows per order | `payment_sequential` up to 29 | **Leave** | Real split payments. Sum per order at analysis time |
| 1 order with no payment record | referential integrity check | **Leave** | Handled with a left join. Dropping the order would destroy information |

Verified: row count unchanged, flags sum to 2 and 82, payment sum identical to raw.

## order_reviews

| Issue | Evidence | Action | Why |
|---|---|---|---|
| Several reviews for one order | 547 orders (1,098 rows), 202 of them with different scores | **Drop** older reviews, keep the latest `review_answer_timestamp` per order (ties broken by `review_id`) | The latest review is the final opinion, and one row per order prevents join multiplication. Only the older opinion is lost. No order, item or payment is orphaned |
| Same `review_id` on different orders | raw: 789 review IDs (764 on 2 orders, 25 on 3). 578 repeated rows remain after cleaning | **Leave** | Appears to be one review covering several orders. The rows are not duplicates |
| `review_creation_date` and `review_answer_timestamp` stored as text | EDA | **Fix**: convert to datetime | Plain fix |
| Comment title (87,123 null) and message (57,898 null) | optional fields | **Leave** and add `has_comment` | A null means no comment. Imputing text would invent data |
| 768 orders have no review | EDA | **Leave** | Not every customer reviews |

Verified: 551 rows dropped, 98,673 distinct orders before and after, the kept review is the latest for every order, mean score 4.086 before and after.

## orders

| Issue | Evidence | Action | Why |
|---|---|---|---|
| Five timestamp columns stored as text | EDA | **Fix**: convert to datetime (no `errors="coerce"`) | Null counts unchanged: 0, 160, 1,783, 2,965, 0 |
| Null approval, carrier and delivery dates | status crosstabs | **Leave** | Expected for orders that never got that far (created, approved, invoiced, processing, unavailable, canceled, and shipped for delivery) |
| `delivered` orders with a missing timestamp | 14 missing approval, 2 missing carrier, 8 missing delivery. 23 orders in total (one order is in two groups) | **Flag** (`flag_delivered_missing_date`) | Contradicts the status, and the true dates are unknown |
| 6 `canceled` orders have a delivery date, 75 have a carrier date | status crosstabs | **Leave** | An order can be canceled after shipping or delivery |
| Carrier handover before payment approval | 1,359 rows. Median gap 0.72 days, 901 under a day, 444 of 1-7 days, 13 of 7-30 days, 1 over 30 (max 171 days). 1,350 delivered, 9 shipped | **Flag** (`flag_carrier_before_approval`), dates not corrected | Looks like timing lag between systems. Which timestamp is off cannot be known |
| Customer delivery before carrier handover | 23 rows, all `delivered`. Median gap 1.66 days, max 16.1 days | **Flag** (`flag_delivery_before_carrier`), dates not corrected | At least one timestamp is wrong. Purchase-to-delivery dates are consistent, so the carrier timestamp is the more likely culprit (a hypothesis). Analyses of handover-to-delivery time should exclude these rows |
| 775 orders with no items, 768 with no review, 1 with no payment | referential integrity check | **Leave** | Real gaps, handled with left joins |

Note: `flag_delivery_before_carrier` and `flag_delivered_missing_date` both have 23 rows but are different sets of orders. They cannot overlap.

Verified: `order_id` unique, 99,441 rows, null counts unchanged, flag sums 1,359, 23, 23.

## products

| Issue | Evidence | Action | Why |
|---|---|---|---|
| 610 products with no category, name length, description length and photo count | all four empty on the same rows | **Fix**: category set to `"unknown"`. The other three columns stay null | The products have real sales. An empty category would vanish from group-bys, while `"unknown"` stays visible |
| 2 products with no weight and no dimensions | EDA | **Leave** | The true values are unknown |
| 4 products with weight exactly 0 g | all `cama_mesa_banho`, 1 photo, identical 30 x 25 x 30 cm | **Fix**: weight set to null, and **Flag** (`flag_zero_weight`) | A box that size cannot weigh 0 g. Null means unknown and avoids dragging averages down. Weight is now null in 6 rows |
| Misspelled column names | `product_name_lenght`, `product_description_lenght` | **Fix**: renamed to `length` | Source typos |
| Counts and sizes stored as floats | caused by the nulls | **Leave** | Values are correct. Cosmetic only |
| Weight flagged as IQR outlier (4,551 rows) | right-skewed | **Leave** | Normal skew |
| 13 products use categories with no English translation | `pc_gamer` (3), `portateis_cozinha_e_preparadores_de_alimentos` (10) | Handled in the translation table | See below |

Verified: 32,951 rows, null changes are exactly category -610 and weight +4, zero untranslated products.

## product_category_name_translation

| Issue | Action | Why |
|---|---|---|
| 2 categories used by products are missing | **Fix**: add `pc_gamer` -> `pc_gamer` and `portateis_cozinha_e_preparadores_de_alimentos` -> `portable_kitchen_and_food_preparers` | The English names are my own wording, not official Olist names |
| `"unknown"` category created in products | **Fix**: add `unknown` -> `unknown` | Keeps those 610 products joinable |

Result: 74 rows (71 + 3).

## sellers

| Issue | Evidence | Action | Why |
|---|---|---|---|
| `seller_zip_code_prefix` stored as `int64` | EDA | **Fix**: 5-character text | Same as customers |
| City spelling variants | 3 rows: `são paulo` (1), `santa barbara d´oeste` (2) | **Fix**: lowercase, trim, remove accents | Merges them into `sao paulo` and `santa barbara d oeste`. Only those 3 rows changed |
| 7 seller rows with zip prefixes not in geolocation | referential integrity check | **Leave** | Coordinates cannot be invented |

Verified: 2,246 distinct zips before and after, all length 5, round trip matches raw, re-validation empty.

---

## Findings that remain after cleaning (expected)

| Table | Remaining finding | Reason |
|---|---|---|
| orders | 160, 1,783 and 2,965 null timestamps | Expected nulls |
| orders | date-order violations (1,359 and 23) | Flagged, not corrected |
| order_items | 383 zero freight values | Free shipping |
| order_reviews | 578 repeated `review_id`, comment nulls | One review covering several orders, optional fields |
| products | nulls in name length, description length, photo count, weight and dimensions | Unknown values |
| customers, sellers | 279 and 7 rows with no geolocation | Known limitation |

## Raw vs cleaned comparison

- Row counts differ only in order_reviews (-551), geolocation (-981,153) and the translation table (+3).
- Columns added are only flags and `has_comment`. Columns removed are only the two misspelled products columns, which were renamed.
- Null counts changed only in products (category -610, weight +4) and order_reviews (comment title -533, message -349, from the dropped reviews).
- Price, freight and payment sums are identical to raw. The review score mean is 4.086 in both. All order IDs are still present.

## Open items

- [ ] Confirm the parquet round trip: zip prefixes read back as text with leading zeros, timestamps as datetimes, flags intact.
- [ ] Check the 775 orders with no items against `order_status`.
- [ ] Inspect the most expensive items individually before relying on them.
- [ ] The nightly-batch explanation for the 1,359 approval-lag rows is untested (check the hour distribution of `order_approved_at`).
- [ ] Payment totals for the 80 orders with a missing first payment were not compared against item totals.
- [ ] Categorical checks ran without allowed-value lists. `order_status` has 8 values and `payment_type` has 5, but state codes were only checked for spelling variants.