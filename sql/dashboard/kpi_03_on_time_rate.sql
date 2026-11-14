-- KPI tile: on-time delivery rate across delivered orders.
-- On time = delivered on or before the estimated delivery date.
SELECT
    round(100.0 * count(*) FILTER (WHERE NOT is_late) / count(*), 2) AS on_time_rate_pct,
    count(*) FILTER (WHERE NOT is_late)                              AS on_time_orders,
    count(*)                                                         AS delivered_orders
FROM v_orders
WHERE is_late IS NOT NULL;
