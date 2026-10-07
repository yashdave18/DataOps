-- ONE ROW = ONE CATEGORY. Ratings count each category/order pair once.
WITH items AS (
    SELECT i.*, COALESCE(t.product_category_name_english, p.product_category_name, 'unknown') AS category,
           r.review_score
    FROM olist.order_items i
    JOIN olist.products p USING (product_id)
    LEFT JOIN olist.category_translation t USING (product_category_name)
    LEFT JOIN olist.order_reviews r USING (order_id)
), sales AS (
    SELECT category, COUNT(*) AS units, COUNT(DISTINCT order_id) AS order_count,
           SUM(price) AS item_revenue, SUM(freight_value) AS freight
    FROM items GROUP BY category
), reviews AS (
    SELECT category, AVG(review_score) AS average_review_score, COUNT(review_score) AS reviewed_orders
    FROM (SELECT DISTINCT category, order_id, review_score FROM items) distinct_orders
    GROUP BY category
)
SELECT s.*, r.average_review_score, r.reviewed_orders,
       DENSE_RANK() OVER (ORDER BY s.item_revenue DESC NULLS LAST) AS revenue_rank
FROM sales s JOIN reviews r USING (category)
ORDER BY item_revenue DESC NULLS LAST, category;
