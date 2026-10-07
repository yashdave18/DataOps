CREATE SCHEMA IF NOT EXISTS warehouse;
-- Type 1 snapshot dimensions. Surrogate keys are local to each full refresh.
CREATE TABLE IF NOT EXISTS warehouse.dim_customer (
    customer_key bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_unique_id text NOT NULL UNIQUE
);
-- Union of known ZIPs, including ZIPs with no geolocation coverage.
CREATE TABLE IF NOT EXISTS warehouse.dim_geography (
    geography_key bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    zip_code_prefix text NOT NULL UNIQUE,
    city text, state text, latitude double precision, longitude double precision,
    has_coordinates boolean NOT NULL
);
CREATE TABLE IF NOT EXISTS warehouse.dim_product (
    product_key bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    product_id text NOT NULL UNIQUE,
    category text, category_english text,
    product_weight_g double precision, product_length_cm double precision,
    product_height_cm double precision, product_width_cm double precision,
    product_photos_qty double precision, flag_zero_weight boolean NOT NULL
);
CREATE TABLE IF NOT EXISTS warehouse.dim_seller (
    seller_key bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    seller_id text NOT NULL UNIQUE,
    city text, state text,
    geography_key bigint REFERENCES warehouse.dim_geography
);
-- Date surrogate is YYYYMMDD; role-playing references in fact_orders.
CREATE TABLE IF NOT EXISTS warehouse.dim_date (
    date_key integer PRIMARY KEY,
    full_date date NOT NULL UNIQUE,
    year integer NOT NULL, quarter integer NOT NULL, month integer NOT NULL,
    day integer NOT NULL, iso_week integer NOT NULL, iso_weekday integer NOT NULL
);
-- ONE ROW = ONE ORDER; payment totals occur only here, never repeated on items.
CREATE TABLE IF NOT EXISTS warehouse.fact_orders (
    order_id text PRIMARY KEY,
    customer_key bigint NOT NULL REFERENCES warehouse.dim_customer,
    geography_key bigint REFERENCES warehouse.dim_geography,
    purchase_date_key integer NOT NULL REFERENCES warehouse.dim_date,
    approval_date_key integer REFERENCES warehouse.dim_date,
    carrier_date_key integer REFERENCES warehouse.dim_date,
    delivery_date_key integer REFERENCES warehouse.dim_date,
    estimated_date_key integer REFERENCES warehouse.dim_date,
    order_status text NOT NULL,
    item_count bigint NOT NULL,
    payment_count bigint NOT NULL,
    total_item_value numeric(18,2), total_freight numeric(18,2), total_payment numeric(18,2),
    review_score integer, has_comment boolean,
    delivery_duration_days double precision, delivery_delay_days integer, is_late boolean,
    flag_carrier_before_approval boolean NOT NULL,
    flag_delivery_before_carrier boolean NOT NULL,
    flag_delivered_missing_date boolean NOT NULL
);
CREATE INDEX IF NOT EXISTS fact_orders_customer_idx ON warehouse.fact_orders (customer_key);
CREATE INDEX IF NOT EXISTS fact_orders_date_idx ON warehouse.fact_orders (purchase_date_key);
CREATE INDEX IF NOT EXISTS fact_orders_geography_idx ON warehouse.fact_orders (geography_key);
-- ONE ROW = ONE ORDER ITEM. Unit count is 1; price and freight are additive.
CREATE TABLE IF NOT EXISTS warehouse.fact_order_items (
    order_id text NOT NULL REFERENCES warehouse.fact_orders,
    order_item_id integer NOT NULL,
    customer_key bigint NOT NULL REFERENCES warehouse.dim_customer,
    product_key bigint NOT NULL REFERENCES warehouse.dim_product,
    seller_key bigint NOT NULL REFERENCES warehouse.dim_seller,
    purchase_date_key integer NOT NULL REFERENCES warehouse.dim_date,
    units integer NOT NULL CHECK (units = 1),
    price numeric(18,2), freight_value numeric(18,2),
    PRIMARY KEY (order_id, order_item_id)
);
CREATE INDEX IF NOT EXISTS fact_items_product_idx ON warehouse.fact_order_items (product_key);
CREATE INDEX IF NOT EXISTS fact_items_seller_idx ON warehouse.fact_order_items (seller_key);
CREATE INDEX IF NOT EXISTS fact_items_date_idx ON warehouse.fact_order_items (purchase_date_key);
