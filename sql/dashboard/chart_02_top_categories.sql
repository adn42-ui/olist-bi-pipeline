-- Chart: top 10 product categories by revenue, excluding canceled and unavailable orders.
SELECT
    p.category_name_english        AS category,
    round(sum(f.total_value), 2)   AS revenue_brl,
    count(DISTINCT f.order_id)     AS order_count
FROM fact_order_items f
JOIN dim_product p ON p.product_key = f.product_key
WHERE f.order_status NOT IN ('canceled', 'unavailable')
GROUP BY p.category_name_english
ORDER BY revenue_brl DESC
LIMIT 10;
