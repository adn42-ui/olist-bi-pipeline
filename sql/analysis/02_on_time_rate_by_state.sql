-- On-time delivery rate by customer state.
-- Order grain (v_orders), delivered orders with a delivery date only.
-- On time = delivered on or before the estimated delivery date.
SELECT
    c.state                                                      AS customer_state,
    count(*)                                                     AS delivered_orders,
    count(*) FILTER (WHERE NOT o.is_late)                        AS on_time_orders,
    round(100.0 * count(*) FILTER (WHERE NOT o.is_late) / count(*), 2) AS on_time_rate_pct,
    round(avg(o.delivery_days), 2)                               AS avg_delivery_days
FROM v_orders o
JOIN dim_customer c ON c.customer_key = o.customer_key
WHERE o.is_late IS NOT NULL
GROUP BY c.state
ORDER BY on_time_rate_pct DESC, c.state;
