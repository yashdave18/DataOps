-- ONE ROW = SELLER. Order-level delivery/reviews deduplicated before aggregation.
WITH sales AS (
    SELECT seller_id, COUNT(*) AS units, SUM(price) AS item_revenue, SUM(freight_value) AS freight
    FROM olist.order_items GROUP BY seller_id
), seller_orders AS (
    SELECT DISTINCT i.seller_id, o.order_id, o.delivery_duration_days, o.is_late, o.review_score
    FROM olist.order_items i JOIN olist.order_metrics o USING (order_id)
), outcomes AS (
    SELECT seller_id, COUNT(*) AS order_count, AVG(delivery_duration_days) AS average_delivery_days,
           AVG(is_late::integer) AS late_delivery_rate, COUNT(is_late) AS known_delivery_outcomes,
           AVG(review_score) AS average_review_score
    FROM seller_orders GROUP BY seller_id
)
SELECT s.*, o.order_count, o.average_delivery_days, o.late_delivery_rate,
       o.known_delivery_outcomes, o.average_review_score, d.seller_city, d.seller_state
FROM sales s JOIN outcomes o USING (seller_id) JOIN olist.sellers d USING (seller_id)
ORDER BY item_revenue DESC NULLS LAST, seller_id;
