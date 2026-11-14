-- KPI tile: total revenue (item price + freight), excluding canceled and unavailable orders.
SELECT round(sum(total_value), 2) AS total_revenue_brl
FROM fact_order_items
WHERE order_status NOT IN ('canceled', 'unavailable');
