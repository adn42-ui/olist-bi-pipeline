-- Chart: review-score distribution for on-time vs late deliveries.
-- pct_of_status is the share of that delivery status's orders at each score,
-- so the two groups can be compared despite their very different sizes.
SELECT
    CASE WHEN o.is_late THEN 'Late' ELSE 'On time' END              AS delivery_status,
    r.review_score,
    count(*)                                                        AS order_count,
    round(100.0 * count(*) / sum(count(*)) OVER (PARTITION BY o.is_late), 2) AS pct_of_status
FROM v_orders o
JOIN v_order_reviews r ON r.order_id = o.order_id
WHERE o.is_late IS NOT NULL
GROUP BY o.is_late, r.review_score
ORDER BY delivery_status DESC, r.review_score;
