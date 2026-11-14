-- KPI tile: total orders, excluding canceled and unavailable orders.
SELECT count(*) AS total_orders
FROM v_orders
WHERE order_status NOT IN ('canceled', 'unavailable');
