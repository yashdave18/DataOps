-- ONE ROW = WHOLE DATASET. Payment AOV excludes orders with unknown payment values.
SELECT COUNT(*) AS order_count, COUNT(DISTINCT customer_unique_id) AS customer_count,
       SUM(total_item_value) AS item_revenue, SUM(total_freight) AS freight,
       SUM(total_payment) AS payments, AVG(total_payment) AS average_order_value,
       COUNT(total_payment) AS known_payment_orders,
       AVG(review_score) AS average_review_score, COUNT(review_score) AS reviewed_orders,
       AVG(is_late::integer) AS late_delivery_rate, COUNT(is_late) AS known_delivery_outcomes,
       (SELECT AVG((frequency > 1)::integer) FROM
           (SELECT customer_unique_id, COUNT(*) AS frequency FROM olist.order_metrics GROUP BY 1) c
       ) AS repeat_customer_rate
FROM olist.order_metrics;
