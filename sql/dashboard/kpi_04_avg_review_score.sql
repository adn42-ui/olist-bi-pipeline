-- KPI tile: average review score (1-5), one review per order.
SELECT
    round(avg(review_score), 2) AS avg_review_score,
    count(*)                    AS reviewed_orders
FROM v_order_reviews;
