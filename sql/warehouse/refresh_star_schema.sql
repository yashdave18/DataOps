-- Rebuild in one transaction with the caller's advisory lock. No CASCADE.
TRUNCATE warehouse.fact_order_items, warehouse.fact_orders,
         warehouse.dim_seller, warehouse.dim_product, warehouse.dim_customer,
         warehouse.dim_geography, warehouse.dim_date RESTART IDENTITY;

INSERT INTO warehouse.dim_customer (customer_unique_id)
SELECT DISTINCT customer_unique_id FROM olist.customers ORDER BY customer_unique_id;

INSERT INTO warehouse.dim_geography (zip_code_prefix, city, state, latitude, longitude, has_coordinates)
SELECT z.zip, g.geolocation_city, g.geolocation_state, g.geolocation_lat, g.geolocation_lng,
       g.geolocation_lat IS NOT NULL AND g.geolocation_lng IS NOT NULL
FROM (
    SELECT geolocation_zip_code_prefix AS zip FROM olist.geolocation
    UNION SELECT customer_zip_code_prefix FROM olist.customers WHERE customer_zip_code_prefix IS NOT NULL
    UNION SELECT seller_zip_code_prefix FROM olist.sellers WHERE seller_zip_code_prefix IS NOT NULL
) z
LEFT JOIN olist.geolocation g ON g.geolocation_zip_code_prefix = z.zip
ORDER BY z.zip;

INSERT INTO warehouse.dim_product
    (product_id, category, category_english, product_weight_g, product_length_cm,
     product_height_cm, product_width_cm, product_photos_qty, flag_zero_weight)
SELECT p.product_id, p.product_category_name, t.product_category_name_english,
       p.product_weight_g, p.product_length_cm, p.product_height_cm, p.product_width_cm,
       p.product_photos_qty, p.flag_zero_weight
FROM olist.products p LEFT JOIN olist.category_translation t USING (product_category_name)
ORDER BY p.product_id;

INSERT INTO warehouse.dim_seller (seller_id, city, state, geography_key)
SELECT s.seller_id, s.seller_city, s.seller_state, g.geography_key
FROM olist.sellers s LEFT JOIN warehouse.dim_geography g ON g.zip_code_prefix = s.seller_zip_code_prefix
ORDER BY s.seller_id;

INSERT INTO warehouse.dim_date (date_key, full_date, year, quarter, month, day, iso_week, iso_weekday)
SELECT TO_CHAR(d, 'YYYYMMDD')::integer, d::date,
       EXTRACT(YEAR FROM d)::integer, EXTRACT(QUARTER FROM d)::integer,
       EXTRACT(MONTH FROM d)::integer, EXTRACT(DAY FROM d)::integer,
       EXTRACT(WEEK FROM d)::integer, EXTRACT(ISODOW FROM d)::integer
FROM (
    SELECT MIN(v.dt)::date AS first_date, MAX(v.dt)::date AS last_date
    FROM olist.orders o CROSS JOIN LATERAL (VALUES
        (o.order_purchase_timestamp), (o.order_approved_at),
        (o.order_delivered_carrier_date), (o.order_delivered_customer_date),
        (o.order_estimated_delivery_date)
    ) v(dt)
) bounds
CROSS JOIN LATERAL generate_series(bounds.first_date::timestamp, bounds.last_date::timestamp, INTERVAL '1 day') d;

INSERT INTO warehouse.fact_orders (
    order_id, customer_key, geography_key, purchase_date_key, approval_date_key,
    carrier_date_key, delivery_date_key, estimated_date_key, order_status,
    item_count, payment_count, total_item_value, total_freight, total_payment,
    review_score, has_comment, delivery_duration_days, delivery_delay_days, is_late,
    flag_carrier_before_approval, flag_delivery_before_carrier, flag_delivered_missing_date
)
SELECT o.order_id, c.customer_key, g.geography_key,
       TO_CHAR(o.order_purchase_timestamp, 'YYYYMMDD')::integer,
       TO_CHAR(o.order_approved_at, 'YYYYMMDD')::integer,
       TO_CHAR(o.order_delivered_carrier_date, 'YYYYMMDD')::integer,
       TO_CHAR(o.order_delivered_customer_date, 'YYYYMMDD')::integer,
       TO_CHAR(o.order_estimated_delivery_date, 'YYYYMMDD')::integer,
       o.order_status, o.item_count, o.payment_count,
       o.total_item_value, o.total_freight, o.total_payment, o.review_score, o.has_comment,
       o.delivery_duration_days, o.delivery_delay_days, o.is_late,
       o.flag_carrier_before_approval, o.flag_delivery_before_carrier, o.flag_delivered_missing_date
FROM olist.order_metrics o
JOIN warehouse.dim_customer c USING (customer_unique_id)
LEFT JOIN warehouse.dim_geography g ON g.zip_code_prefix = o.customer_zip_code_prefix;

INSERT INTO warehouse.fact_order_items
    (order_id, order_item_id, customer_key, product_key, seller_key, purchase_date_key, units, price, freight_value)
SELECT i.order_id, i.order_item_id, o.customer_key, p.product_key, s.seller_key,
       o.purchase_date_key, 1, i.price, i.freight_value
FROM olist.order_items i
JOIN warehouse.fact_orders o USING (order_id)
JOIN warehouse.dim_product p USING (product_id)
JOIN warehouse.dim_seller s USING (seller_id);
