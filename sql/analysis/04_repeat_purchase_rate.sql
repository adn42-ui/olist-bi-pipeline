-- Repeat-purchase rate: share of customers who placed more than one order.
-- Customers are identified by dim_customer (customer_unique_id), because the
-- source customer_id is generated per order. Canceled and unavailable orders
-- are excluded.
WITH orders_per_customer AS (
    SELECT customer_key, count(*) AS order_count
    FROM v_orders
    WHERE order_status NOT IN ('canceled', 'unavailable')
    GROUP BY customer_key
)
SELECT
    count(*)                                             AS customers,
    count(*) FILTER (WHERE order_count >= 2)             AS repeat_customers,
    round(100.0 * count(*) FILTER (WHERE order_count >= 2) / count(*), 2) AS repeat_purchase_rate_pct,
    max(order_count)                                     AS max_orders_by_one_customer
FROM orders_per_customer;
