-- Cleaned relational model. All timestamps are naive source-local timestamps.
CREATE SCHEMA IF NOT EXISTS olist;

-- ONE ROW = ONE ZIP PREFIX. Missing coordinate coverage is permitted elsewhere.
CREATE TABLE IF NOT EXISTS olist.geolocation (
    geolocation_zip_code_prefix text PRIMARY KEY CHECK (geolocation_zip_code_prefix ~ '^[0-9]{5}$'),
    geolocation_lat double precision,
    geolocation_lng double precision,
    geolocation_city text,
    geolocation_state text
);
CREATE TABLE IF NOT EXISTS olist.category_translation (
    product_category_name text PRIMARY KEY,
    product_category_name_english text
);
-- ONE ROW = ONE ORDER-LINKED CUSTOMER RECORD, not one person.
CREATE TABLE IF NOT EXISTS olist.customers (
    customer_id text PRIMARY KEY,
    customer_unique_id text NOT NULL,
    customer_zip_code_prefix text CHECK (customer_zip_code_prefix ~ '^[0-9]{5}$'),
    customer_city text,
    customer_state text
);
CREATE INDEX IF NOT EXISTS customers_unique_id_idx ON olist.customers (customer_unique_id);
CREATE TABLE IF NOT EXISTS olist.products (
    product_id text PRIMARY KEY,
    product_category_name text,
    product_name_length double precision,
    product_description_length double precision,
    product_photos_qty double precision,
    product_weight_g double precision,
    product_length_cm double precision,
    product_height_cm double precision,
    product_width_cm double precision,
    flag_zero_weight boolean NOT NULL
);
-- No category FK: untranslatable categories must remain visible.
CREATE TABLE IF NOT EXISTS olist.sellers (
    seller_id text PRIMARY KEY,
    seller_zip_code_prefix text CHECK (seller_zip_code_prefix ~ '^[0-9]{5}$'),
    seller_city text,
    seller_state text
);
-- ONE ROW = ONE ORDER. Uncertain chronology is flagged, not constrained away.
CREATE TABLE IF NOT EXISTS olist.orders (
    order_id text PRIMARY KEY,
    customer_id text NOT NULL REFERENCES olist.customers (customer_id),
    order_status text NOT NULL,
    order_purchase_timestamp timestamp NOT NULL,
    order_approved_at timestamp,
    order_delivered_carrier_date timestamp,
    order_delivered_customer_date timestamp,
    order_estimated_delivery_date timestamp,
    flag_carrier_before_approval boolean NOT NULL,
    flag_delivery_before_carrier boolean NOT NULL,
    flag_delivered_missing_date boolean NOT NULL
);
CREATE INDEX IF NOT EXISTS orders_customer_idx ON olist.orders (customer_id);
CREATE INDEX IF NOT EXISTS orders_purchase_idx ON olist.orders (order_purchase_timestamp);
CREATE INDEX IF NOT EXISTS orders_status_idx ON olist.orders (order_status);
-- ONE ROW = ONE UNIT / ITEM WITHIN AN ORDER.
CREATE TABLE IF NOT EXISTS olist.order_items (
    order_id text NOT NULL REFERENCES olist.orders (order_id),
    order_item_id integer NOT NULL CHECK (order_item_id > 0),
    product_id text NOT NULL REFERENCES olist.products (product_id),
    seller_id text NOT NULL REFERENCES olist.sellers (seller_id),
    shipping_limit_date timestamp,
    price numeric(18,2) CHECK (price >= 0),
    freight_value numeric(18,2) CHECK (freight_value >= 0),
    PRIMARY KEY (order_id, order_item_id)
);
CREATE INDEX IF NOT EXISTS items_product_idx ON olist.order_items (product_id);
CREATE INDEX IF NOT EXISTS items_seller_idx ON olist.order_items (seller_id);
-- ONE ROW = ONE PAYMENT COMPONENT; zero installments remain flagged.
CREATE TABLE IF NOT EXISTS olist.order_payments (
    order_id text NOT NULL REFERENCES olist.orders (order_id),
    payment_sequential integer NOT NULL CHECK (payment_sequential > 0),
    payment_type text,
    payment_installments integer,
    payment_value numeric(18,2) CHECK (payment_value >= 0),
    flag_zero_installments boolean NOT NULL,
    flag_missing_first_payment boolean NOT NULL,
    PRIMARY KEY (order_id, payment_sequential)
);
-- ONE ROW = ONE LATEST RETAINED REVIEW PER ORDER. review_id is NOT unique.
CREATE TABLE IF NOT EXISTS olist.order_reviews (
    order_id text PRIMARY KEY REFERENCES olist.orders (order_id),
    review_id text NOT NULL,
    review_score integer CHECK (review_score BETWEEN 1 AND 5),
    review_comment_title text,
    review_comment_message text,
    review_creation_date timestamp,
    review_answer_timestamp timestamp,
    has_comment boolean NOT NULL
);

-- ONE ROW = ONE ORDER. Child tables are aggregated independently before joining.
CREATE OR REPLACE VIEW olist.order_metrics AS
WITH items AS (
    SELECT order_id, SUM(price) AS total_item_value, SUM(freight_value) AS total_freight,
           COUNT(*) AS item_count
    FROM olist.order_items GROUP BY order_id
), payments AS (
    SELECT order_id, SUM(payment_value) AS total_payment, COUNT(*) AS payment_count
    FROM olist.order_payments GROUP BY order_id
)
SELECT o.*, c.customer_unique_id, c.customer_zip_code_prefix, c.customer_city, c.customer_state,
       i.total_item_value, i.total_freight, COALESCE(i.item_count, 0) AS item_count,
       p.total_payment, COALESCE(p.payment_count, 0) AS payment_count,
       r.review_score, r.has_comment,
       EXTRACT(EPOCH FROM (o.order_delivered_customer_date - o.order_purchase_timestamp)) / 86400.0
           AS delivery_duration_days,
       o.order_delivered_customer_date::date - o.order_estimated_delivery_date::date AS delivery_delay_days,
       o.order_delivered_customer_date::date > o.order_estimated_delivery_date::date AS is_late
FROM olist.orders o
JOIN olist.customers c USING (customer_id)
LEFT JOIN items i USING (order_id)
LEFT JOIN payments p USING (order_id)
LEFT JOIN olist.order_reviews r USING (order_id);
