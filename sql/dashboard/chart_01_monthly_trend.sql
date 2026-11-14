-- Chart: monthly revenue and order count, complete months only (2017-01 to 2018-08).
-- Excludes canceled and unavailable orders.
SELECT
    d.year_month,
    round(sum(f.total_value), 2)  AS revenue_brl,
    count(DISTINCT f.order_id)    AS order_count
FROM fact_order_items f
JOIN dim_date d ON d.date_key = f.purchase_date_key
WHERE f.order_status NOT IN ('canceled', 'unavailable')
  AND d.year_month BETWEEN '2017-01' AND '2018-08'
GROUP BY d.year_month
ORDER BY d.year_month;
