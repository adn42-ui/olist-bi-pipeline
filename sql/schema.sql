-- =============================================================================
-- Olist star schema (DuckDB)
--
-- Source: the raw.* tables loaded by src/ingest.py.
-- This script is idempotent: it drops and rebuilds every object it owns.
--
-- GRAIN
--   fact_order_items      one row per ORDER ITEM (order_id + order_item_id).
--                         An order with 3 items has 3 rows.
--   fact_order_payments   one row per payment on an order (order grain or finer).
--   fact_order_reviews    one row per review of an order.
--   Payments and reviews are deliberately NOT joined onto fact_order_items:
--   they describe the whole order, so joining them to items would repeat
--   (double count) them once per item.
--
-- KEYS
--   Dimensions use integer surrogate keys (*_key) and keep the source system's
--   natural key as a unique column. order_id is a degenerate dimension: it
--   lives on the fact tables and has no dimension table of its own.
--
-- MEASURES
--   Revenue = price + freight_value, summed from fact_order_items.
-- =============================================================================

-- Drop in dependency order: views, then facts, then dimensions.
DROP VIEW  IF EXISTS v_orders;
DROP VIEW  IF EXISTS v_order_reviews;
DROP TABLE IF EXISTS fact_order_reviews;
DROP TABLE IF EXISTS fact_order_payments;
DROP TABLE IF EXISTS fact_order_items;
DROP TABLE IF EXISTS dim_customer;
DROP TABLE IF EXISTS dim_product;
DROP TABLE IF EXISTS dim_seller;
DROP TABLE IF EXISTS dim_date;

-- -----------------------------------------------------------------------------
-- dim_date: one row per calendar day covering every date in the orders table.
-- Key is an integer in YYYYMMDD form (e.g. 20180315).
-- -----------------------------------------------------------------------------
CREATE TABLE dim_date (
    date_key      INTEGER PRIMARY KEY,   -- YYYYMMDD
    full_date     DATE    NOT NULL UNIQUE,
    year          INTEGER NOT NULL,
    quarter       INTEGER NOT NULL,
    month         INTEGER NOT NULL,
    month_name    VARCHAR NOT NULL,
    year_month    VARCHAR NOT NULL,      -- 'YYYY-MM', convenient for trend charts
    day_of_month  INTEGER NOT NULL,
    day_of_week   INTEGER NOT NULL,      -- ISO: 1 = Monday ... 7 = Sunday
    day_name      VARCHAR NOT NULL,
    is_weekend    BOOLEAN NOT NULL
);

INSERT INTO dim_date
SELECT
    CAST(strftime(d, '%Y%m%d') AS INTEGER),
    d,
    year(d),
    quarter(d),
    month(d),
    monthname(d),
    strftime(d, '%Y-%m'),
    day(d),
    isodow(d),
    dayname(d),
    isodow(d) IN (6, 7)
FROM (
    SELECT CAST(unnest(generate_series(
        (SELECT CAST(min(order_purchase_timestamp) AS DATE) FROM raw.orders),
        (SELECT CAST(max(greatest(
                    order_purchase_timestamp,
                    coalesce(order_delivered_customer_date, order_purchase_timestamp),
                    order_estimated_delivery_date)) AS DATE)
           FROM raw.orders),
        INTERVAL 1 DAY)) AS DATE) AS d
);

-- -----------------------------------------------------------------------------
-- dim_customer: one row per real person (customer_unique_id).
-- In the source, customer_id is generated per ORDER, so it cannot identify a
-- returning customer; customer_unique_id can. Where a person ordered from more
-- than one address, the location of their most recent order is kept.
-- -----------------------------------------------------------------------------
CREATE TABLE dim_customer (
    customer_key        INTEGER PRIMARY KEY,       -- surrogate key
    customer_unique_id  VARCHAR NOT NULL UNIQUE,   -- natural key
    zip_code_prefix     VARCHAR,
    city                VARCHAR,
    state               VARCHAR NOT NULL           -- 2-letter Brazilian state code
);

INSERT INTO dim_customer
SELECT
    row_number() OVER (ORDER BY customer_unique_id),
    customer_unique_id,
    customer_zip_code_prefix,
    customer_city,
    customer_state
FROM (
    SELECT c.*
    FROM raw.customers c
    JOIN raw.orders o USING (customer_id)
    QUALIFY row_number() OVER (
        PARTITION BY c.customer_unique_id
        ORDER BY o.order_purchase_timestamp DESC, c.customer_id
    ) = 1
);

-- -----------------------------------------------------------------------------
-- dim_product: one row per product. The English category name falls back to
-- the Portuguese name, then to 'unknown', so it is never null.
-- -----------------------------------------------------------------------------
CREATE TABLE dim_product (
    product_key            INTEGER PRIMARY KEY,      -- surrogate key
    product_id             VARCHAR NOT NULL UNIQUE,  -- natural key
    category_name          VARCHAR,                  -- original (Portuguese)
    category_name_english  VARCHAR NOT NULL,
    weight_g               DOUBLE,
    length_cm              DOUBLE,
    height_cm              DOUBLE,
    width_cm               DOUBLE,
    photos_qty             INTEGER
);

INSERT INTO dim_product
SELECT
    row_number() OVER (ORDER BY p.product_id),
    p.product_id,
    p.product_category_name,
    coalesce(t.product_category_name_english, p.product_category_name, 'unknown'),
    p.product_weight_g,
    p.product_length_cm,
    p.product_height_cm,
    p.product_width_cm,
    p.product_photos_qty
FROM raw.products p
LEFT JOIN raw.category_translation t USING (product_category_name);

-- -----------------------------------------------------------------------------
-- dim_seller: one row per seller.
-- -----------------------------------------------------------------------------
CREATE TABLE dim_seller (
    seller_key       INTEGER PRIMARY KEY,      -- surrogate key
    seller_id        VARCHAR NOT NULL UNIQUE,  -- natural key
    zip_code_prefix  VARCHAR,
    city             VARCHAR,
    state            VARCHAR NOT NULL
);

INSERT INTO dim_seller
SELECT
    row_number() OVER (ORDER BY seller_id),
    seller_id,
    seller_zip_code_prefix,
    seller_city,
    seller_state
FROM raw.sellers;

-- -----------------------------------------------------------------------------
-- fact_order_items: GRAIN = one row per order item.
--
-- Primary key:  (order_id, order_item_id)
-- Foreign keys: customer_key, product_key, seller_key, purchase_date_key
--
-- Order-level attributes (status, timestamps, delivery flags) are repeated on
-- every item row of the order. Use the v_orders view for order-level metrics
-- so multi-item orders are not counted more than once.
--
-- is_late: delivered orders only. An order is late when its delivery DATE is
-- after the estimated delivery DATE (the estimate has no time of day, so a
-- delivery on the estimated day counts as on time). NULL when the order was
-- not delivered or has no delivery date.
-- -----------------------------------------------------------------------------
CREATE TABLE fact_order_items (
    order_id                  VARCHAR   NOT NULL,   -- degenerate dimension
    order_item_id             INTEGER   NOT NULL,   -- item sequence within the order
    customer_key              INTEGER   NOT NULL REFERENCES dim_customer (customer_key),
    product_key               INTEGER   NOT NULL REFERENCES dim_product  (product_key),
    seller_key                INTEGER   NOT NULL REFERENCES dim_seller   (seller_key),
    purchase_date_key         INTEGER   NOT NULL REFERENCES dim_date     (date_key),
    order_status              VARCHAR   NOT NULL,
    purchase_ts               TIMESTAMP NOT NULL,
    delivered_customer_ts     TIMESTAMP,
    estimated_delivery_date   DATE      NOT NULL,
    price                     DOUBLE    NOT NULL,   -- item price, BRL
    freight_value             DOUBLE    NOT NULL,   -- freight charged for this item, BRL
    total_value               DOUBLE    NOT NULL,   -- price + freight_value
    delivery_days             DOUBLE,               -- purchase -> delivery, fractional days
    is_late                   BOOLEAN,              -- see definition above
    PRIMARY KEY (order_id, order_item_id)
);

INSERT INTO fact_order_items
SELECT
    oi.order_id,
    oi.order_item_id,
    dc.customer_key,
    dp.product_key,
    ds.seller_key,
    CAST(strftime(o.order_purchase_timestamp, '%Y%m%d') AS INTEGER),
    o.order_status,
    o.order_purchase_timestamp,
    o.order_delivered_customer_date,
    CAST(o.order_estimated_delivery_date AS DATE),
    oi.price,
    oi.freight_value,
    oi.price + oi.freight_value,
    CASE WHEN o.order_status = 'delivered'
         THEN epoch(o.order_delivered_customer_date - o.order_purchase_timestamp) / 86400.0
    END,
    CASE WHEN o.order_status = 'delivered' AND o.order_delivered_customer_date IS NOT NULL
         THEN CAST(o.order_delivered_customer_date AS DATE)
              > CAST(o.order_estimated_delivery_date AS DATE)
    END
FROM raw.order_items oi
JOIN raw.orders    o  ON o.order_id = oi.order_id
JOIN raw.customers c  ON c.customer_id = o.customer_id
JOIN dim_customer  dc ON dc.customer_unique_id = c.customer_unique_id
JOIN dim_product   dp ON dp.product_id = oi.product_id
JOIN dim_seller    ds ON ds.seller_id = oi.seller_id;

-- -----------------------------------------------------------------------------
-- fact_order_payments: GRAIN = one row per payment record on an order.
-- Primary key: (order_id, payment_sequential). Links to orders via order_id.
-- -----------------------------------------------------------------------------
CREATE TABLE fact_order_payments (
    order_id              VARCHAR NOT NULL,
    payment_sequential    INTEGER NOT NULL,
    payment_type          VARCHAR,
    payment_installments  INTEGER,
    payment_value         DOUBLE  NOT NULL,
    PRIMARY KEY (order_id, payment_sequential)
);

INSERT INTO fact_order_payments
SELECT order_id, payment_sequential, payment_type, payment_installments, payment_value
FROM raw.order_payments;

-- -----------------------------------------------------------------------------
-- fact_order_reviews: GRAIN = one row per (review, order).
-- Primary key: (review_id, order_id). review_id alone is not unique in the
-- source, and an order can have more than one review.
-- -----------------------------------------------------------------------------
CREATE TABLE fact_order_reviews (
    review_id         VARCHAR   NOT NULL,
    order_id          VARCHAR   NOT NULL,
    review_score      INTEGER   NOT NULL,   -- 1 (worst) to 5 (best)
    review_created_ts TIMESTAMP,
    review_answer_ts  TIMESTAMP,
    PRIMARY KEY (review_id, order_id)
);

INSERT INTO fact_order_reviews
SELECT review_id, order_id, review_score, review_creation_date, review_answer_timestamp
FROM raw.order_reviews;

-- -----------------------------------------------------------------------------
-- v_order_reviews: exactly one review per order (the most recently answered),
-- so order-level joins never fan out.
-- -----------------------------------------------------------------------------
CREATE VIEW v_order_reviews AS
SELECT order_id, review_id, review_score, review_created_ts
FROM fact_order_reviews
QUALIFY row_number() OVER (
    PARTITION BY order_id
    ORDER BY review_answer_ts DESC, review_id
) = 1;

-- -----------------------------------------------------------------------------
-- v_orders: fact_order_items rolled up to ORDER grain (one row per order).
-- Use this for order counts, on-time rates and anything else that should
-- count an order once regardless of how many items it has.
-- -----------------------------------------------------------------------------
CREATE VIEW v_orders AS
SELECT
    order_id,
    any_value(customer_key)            AS customer_key,
    any_value(purchase_date_key)       AS purchase_date_key,
    any_value(order_status)            AS order_status,
    any_value(purchase_ts)             AS purchase_ts,
    any_value(delivered_customer_ts)   AS delivered_customer_ts,
    any_value(estimated_delivery_date) AS estimated_delivery_date,
    any_value(delivery_days)           AS delivery_days,
    any_value(is_late)                 AS is_late,
    count(*)                           AS item_count,
    sum(price)                         AS items_value,
    sum(freight_value)                 AS freight_value,
    sum(total_value)                   AS order_value
FROM fact_order_items
GROUP BY order_id;
