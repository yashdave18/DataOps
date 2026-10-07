-- Run individual statements in psql or your SQL editor. All statuses unless stated.

-- SELECT, WHERE, CASE: delivered orders with known lateness.
SELECT order_id, total_payment,
       CASE WHEN is_late THEN 'late' WHEN NOT is_late THEN 'on_time' ELSE 'unknown' END AS outcome
FROM olist.order_metrics WHERE order_status = 'delivered'
ORDER BY order_purchase_timestamp DESC LIMIT 100;

-- GROUP BY, HAVING: repeat customers, preserving person-level identity.
SELECT customer_unique_id, COUNT(*) AS order_count, SUM(total_payment) AS observed_spend
FROM olist.order_metrics GROUP BY customer_unique_id HAVING COUNT(*) > 1
ORDER BY observed_spend DESC NULLS LAST;

-- Conditional aggregation and a meaningful delivery denominator.
SELECT order_status, COUNT(*) AS orders,
       COUNT(*) FILTER (WHERE is_late) AS late_orders, COUNT(is_late) AS known_outcomes,
       AVG(is_late::integer) AS late_rate,
       SUM(total_freight) / NULLIF(SUM(total_item_value), 0) AS freight_to_item_value
FROM olist.order_metrics GROUP BY order_status ORDER BY order_status;

-- Review relationship: association, not evidence of causation.
SELECT CASE WHEN is_late THEN 'late' WHEN NOT is_late THEN 'on_time' ELSE 'unknown' END AS outcome,
       COUNT(review_score) AS reviewed_orders, AVG(review_score) AS average_review_score
FROM olist.order_metrics GROUP BY 1 ORDER BY 1;

-- Subquery: orders whose known payment is above the dataset mean.
SELECT order_id, total_payment FROM olist.order_metrics
WHERE total_payment > (SELECT AVG(total_payment) FROM olist.order_metrics)
ORDER BY total_payment DESC LIMIT 100;

-- Star schema: never sum order-level payment after joining it to item facts.
SELECT d.year, d.month, p.category_english, SUM(i.units) AS units, SUM(i.price) AS item_revenue
FROM warehouse.fact_order_items i
JOIN warehouse.dim_date d ON d.date_key = i.purchase_date_key
JOIN warehouse.dim_product p USING (product_key)
GROUP BY d.year, d.month, p.category_english ORDER BY d.year, d.month, item_revenue DESC;
