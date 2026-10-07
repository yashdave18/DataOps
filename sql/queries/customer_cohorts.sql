-- ONE ROW = COHORT / OBSERVABLE MONTH OFFSET. Future periods are not zero-filled.
WITH activity AS (
    SELECT DISTINCT customer_unique_id, DATE_TRUNC('month', order_purchase_timestamp)::date AS month
    FROM olist.order_metrics
), first_purchase AS (
    SELECT customer_unique_id, MIN(month) AS cohort_month FROM activity GROUP BY 1
), sizes AS (
    SELECT cohort_month, COUNT(*) AS cohort_size FROM first_purchase GROUP BY 1
), active AS (
    SELECT f.cohort_month, a.month, COUNT(*) AS customers
    FROM activity a JOIN first_purchase f USING (customer_unique_id) GROUP BY 1, 2
), grid AS (
    SELECT s.*, m::date AS month
    FROM sizes s CROSS JOIN LATERAL generate_series(
        s.cohort_month::timestamp, (SELECT MAX(month)::timestamp FROM activity), INTERVAL '1 month'
    ) m
)
SELECT g.cohort_month::timestamp,
       ((EXTRACT(YEAR FROM g.month) - EXTRACT(YEAR FROM g.cohort_month)) * 12
        + EXTRACT(MONTH FROM g.month) - EXTRACT(MONTH FROM g.cohort_month))::integer AS month_offset,
       COALESCE(a.customers, 0) AS customers, g.cohort_size,
       COALESCE(a.customers, 0)::double precision / g.cohort_size AS retention_rate
FROM grid g LEFT JOIN active a USING (cohort_month, month)
ORDER BY cohort_month, month_offset;
