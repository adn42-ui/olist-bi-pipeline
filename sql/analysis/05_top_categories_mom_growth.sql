-- Top 10 product categories by revenue, with month-over-month growth.
-- Revenue = item price + freight; canceled and unavailable orders excluded.
-- The ranking uses all-time revenue. The monthly series is limited to
-- 2017-01 .. 2018-08, the months with complete data (earlier and later months
-- hold between 1 and 290 orders; see 01_monthly_revenue_orders.sql).
-- A month spine is cross-joined to the categories so a month with no sales
-- shows as 0 revenue instead of silently disappearing from the LAG.
WITH sales AS (
    SELECT p.category_name_english AS category, d.year_month, f.total_value
    FROM fact_order_items f
    JOIN dim_product p ON p.product_key = f.product_key
    JOIN dim_date    d ON d.date_key = f.purchase_date_key
    WHERE f.order_status NOT IN ('canceled', 'unavailable')
),
top_categories AS (
    SELECT
        category,
        sum(total_value)                                AS total_revenue,
        row_number() OVER (ORDER BY sum(total_value) DESC) AS revenue_rank
    FROM sales
    GROUP BY category
    ORDER BY total_revenue DESC
    LIMIT 10
),
months AS (
    SELECT DISTINCT year_month
    FROM dim_date
    WHERE year_month BETWEEN '2017-01' AND '2018-08'
),
monthly AS (
    SELECT
        t.revenue_rank,
        t.category,
        t.total_revenue,
        m.year_month,
        coalesce(sum(s.total_value), 0) AS revenue
    FROM top_categories t
    CROSS JOIN months m
    LEFT JOIN sales s ON s.category = t.category AND s.year_month = m.year_month
    GROUP BY t.revenue_rank, t.category, t.total_revenue, m.year_month
)
SELECT
    revenue_rank,
    category,
    round(total_revenue, 2)                                         AS total_revenue,
    year_month,
    round(revenue, 2)                                               AS revenue,
    round(lag(revenue) OVER w, 2)                                   AS prev_month_revenue,
    -- NULL for the first month and when the previous month had no revenue.
    round(100.0 * (revenue - lag(revenue) OVER w) / nullif(lag(revenue) OVER w, 0), 2)
                                                                    AS mom_growth_pct
FROM monthly
WINDOW w AS (PARTITION BY category ORDER BY year_month)
ORDER BY revenue_rank, year_month;
