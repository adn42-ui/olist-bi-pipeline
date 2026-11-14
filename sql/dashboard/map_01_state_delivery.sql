-- Map: delivery performance and sales by customer state.
-- state_iso is the ISO 3166-2 code (e.g. BR-SP) that BI tools use to match
-- Brazilian states to map shapes. Delivery metrics use delivered orders only;
-- orders and revenue exclude canceled and unavailable orders.
SELECT
    c.state                                                          AS customer_state,
    'BR-' || c.state                                                 AS state_iso,
    count(*) FILTER (WHERE o.order_status NOT IN ('canceled', 'unavailable')) AS order_count,
    round(sum(o.order_value) FILTER (WHERE o.order_status NOT IN ('canceled', 'unavailable')), 2)
                                                                     AS revenue_brl,
    count(*) FILTER (WHERE o.is_late IS NOT NULL)                    AS delivered_orders,
    round(100.0 * count(*) FILTER (WHERE NOT o.is_late)
          / count(*) FILTER (WHERE o.is_late IS NOT NULL), 2)        AS on_time_rate_pct,
    round(avg(o.delivery_days) FILTER (WHERE o.is_late IS NOT NULL), 2) AS avg_delivery_days
FROM v_orders o
JOIN dim_customer c ON c.customer_key = o.customer_key
GROUP BY c.state
ORDER BY c.state;
