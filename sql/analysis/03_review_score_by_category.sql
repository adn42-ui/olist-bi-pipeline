-- Average review score by product category.
-- Reviews are given per ORDER, not per item, so an order's score is credited
-- once to each distinct category in that order. Orders without a review are
-- excluded. reviewed_orders is included so small categories can be filtered
-- or discounted: averages over a few dozen orders are noisy.
WITH order_categories AS (
    SELECT DISTINCT f.order_id, p.category_name_english AS category
    FROM fact_order_items f
    JOIN dim_product p ON p.product_key = f.product_key
)
SELECT
    oc.category,
    count(*)                         AS reviewed_orders,
    round(avg(r.review_score), 3)    AS avg_review_score,
    round(100.0 * count(*) FILTER (WHERE r.review_score <= 2) / count(*), 2) AS pct_low_scores
FROM order_categories oc
JOIN v_order_reviews r ON r.order_id = oc.order_id
GROUP BY oc.category
ORDER BY avg_review_score DESC, oc.category;
