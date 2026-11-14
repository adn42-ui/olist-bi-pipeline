-- Monthly revenue and order-count trend.
-- Revenue = item price + freight. Canceled and unavailable orders are excluded.
-- Months are by purchase date. The first and last months in the data are
-- partial or near-empty; see the README limitations.
SELECT
    d.year_month,
    count(DISTINCT f.order_id)                                   AS order_count,
    round(sum(f.total_value), 2)                                 AS revenue,
    round(sum(f.total_value) / count(DISTINCT f.order_id), 2)    AS avg_order_value
FROM fact_order_items f
JOIN dim_date d ON d.date_key = f.purchase_date_key
WHERE f.order_status NOT IN ('canceled', 'unavailable')
GROUP BY d.year_month
ORDER BY d.year_month;
