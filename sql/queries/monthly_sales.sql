-- ONE ROW = ONE OBSERVED PURCHASE MONTH; all statuses. Child sums are in the view.
WITH monthly AS (
    SELECT DATE_TRUNC('month', order_purchase_timestamp)::timestamp AS month,
           COUNT(*) AS order_count, COUNT(DISTINCT customer_unique_id) AS customer_count,
           SUM(total_item_value) AS item_revenue, SUM(total_freight) AS freight,
           SUM(total_payment) AS payments, AVG(total_payment) AS average_order_value,
           COUNT(review_score) AS reviewed_orders, AVG(review_score) AS average_review_score
    FROM olist.order_metrics GROUP BY 1
)
SELECT *, order_count::double precision / NULLIF(LAG(order_count) OVER (ORDER BY month), 0) - 1 AS order_growth_rate,
       SUM(item_revenue) OVER (ORDER BY month ROWS UNBOUNDED PRECEDING) AS running_item_revenue
FROM monthly ORDER BY month;
