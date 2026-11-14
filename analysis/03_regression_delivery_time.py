"""Linear regression: delivery time (days) ~ distance proxy + product weight.

Unit of analysis: one delivered order.
  delivery_days    purchase -> delivery to customer, in days (outcome)
  different_state  1 if any seller on the order is in a different state from
                   the customer, else 0 (the distance proxy)
  weight_kg        total weight of the items on the order, in kg

Orders containing a product with missing or zero weight are excluded.
Standard errors are heteroskedasticity-robust (HC3) because delivery time is
right-skewed with a long tail.

Run with:  python analysis/03_regression_delivery_time.py
"""
import matplotlib.pyplot as plt
import numpy as np
import statsmodels.formula.api as smf

import stats_common as sc

DATA_SQL = """
SELECT
    f.order_id,
    any_value(f.delivery_days)                      AS delivery_days,
    max(CAST(s.state <> c.state AS INTEGER))        AS different_state,
    sum(p.weight_g) / 1000.0                        AS weight_kg
FROM fact_order_items f
JOIN dim_customer c ON c.customer_key = f.customer_key
JOIN dim_seller   s ON s.seller_key   = f.seller_key
JOIN dim_product  p ON p.product_key  = f.product_key
WHERE f.order_status = 'delivered' AND f.delivery_days IS NOT NULL
GROUP BY f.order_id
HAVING count(*) FILTER (WHERE p.weight_g IS NULL OR p.weight_g <= 0) = 0
-- Fixed row order keeps floating-point sums, and so the results, identical across runs.
ORDER BY f.order_id
"""


def main() -> None:
    df = sc.query(DATA_SQL)
    model = smf.ols("delivery_days ~ different_state + weight_kg", data=df).fit(cov_type="HC3")
    ci = model.conf_int()

    coefs = {
        name: {
            "coefficient": round(float(model.params[name]), 4),
            "std_error_hc3": round(float(model.bse[name]), 4),
            "ci95": [round(float(ci.loc[name, 0]), 4), round(float(ci.loc[name, 1]), 4)],
            "p_value": float(f"{model.pvalues[name]:.6g}"),
        }
        for name in model.params.index
    }
    by_state = df.groupby("different_state")["delivery_days"].agg(["count", "mean", "median"])
    result = {
        "model": "OLS: delivery_days ~ different_state + weight_kg (HC3 robust SE)",
        "n": int(model.nobs),
        "r_squared": round(float(model.rsquared), 4),
        "adj_r_squared": round(float(model.rsquared_adj), 4),
        "residual_std_days": round(float(np.sqrt(model.scale)), 2),
        "coefficients": coefs,
        "share_different_state_pct": round(float(df["different_state"].mean() * 100), 2),
        "delivery_days_same_state": {
            "n": int(by_state.loc[0, "count"]),
            "mean": round(float(by_state.loc[0, "mean"]), 2),
            "median": round(float(by_state.loc[0, "median"]), 2),
        },
        "delivery_days_different_state": {
            "n": int(by_state.loc[1, "count"]),
            "mean": round(float(by_state.loc[1, "mean"]), 2),
            "median": round(float(by_state.loc[1, "median"]), 2),
        },
        "weight_kg_median": round(float(df["weight_kg"].median()), 3),
        "weight_kg_p99": round(float(df["weight_kg"].quantile(0.99)), 2),
        "corr_weight_different_state": round(float(df["weight_kg"].corr(df["different_state"])), 3),
    }

    c = coefs
    lines = [
        f"  {name:<16} {v['coefficient']:>9.4f}   SE {v['std_error_hc3']:.4f}   "
        f"95% CI [{v['ci95'][0]:.4f}, {v['ci95'][1]:.4f}]   p {sc.fmt_p(v['p_value'])}"
        for name, v in c.items()
    ]
    report = f"""REGRESSION: delivery_days ~ different_state + weight_kg   (n = {result['n']:,})
{chr(10).join(lines)}
  R-squared = {result['r_squared']}   adjusted = {result['adj_r_squared']}   residual SD = {result['residual_std_days']} days

Interpretation:
  - Baseline (same state, weight 0): {c['Intercept']['coefficient']:.2f} days.
  - Shipping across state lines adds {c['different_state']['coefficient']:.2f} days on average, holding weight fixed.
  - Each extra kg adds {c['weight_kg']['coefficient']:.3f} days ({c['weight_kg']['coefficient'] * 10:.2f} days per 10 kg).
  - The model explains {result['r_squared'] * 100:.1f}% of the variance in delivery time; a typical
    prediction is off by about {result['residual_std_days']} days.

Limitations:
  - Same-state vs different-state is a crude distance proxy. Brazilian states vary
    enormously in size, and neighbouring states are treated the same as opposite
    ends of the country.
  - Delivery time is right-skewed with extreme outliers, so residuals are not
    normal. HC3 robust standard errors address unequal variance, not the skew.
  - Important drivers are omitted: seller handling time, carrier, season,
    remoteness of the destination. Coefficients are associations, not causal effects.
  - Weight is the total catalogue weight of the order, not the shipped parcel weight."""
    sc.save_result("03_regression_delivery_time", result, report)

    # Figure: delivery-time distribution by distance proxy (clipped at 60 days for legibility).
    fig, ax = plt.subplots(figsize=(7, 4))
    bins = np.arange(0, 61, 2)
    same = df.loc[df["different_state"] == 0, "delivery_days"].clip(upper=60)
    diff = df.loc[df["different_state"] == 1, "delivery_days"].clip(upper=60)
    ax.hist(same, bins=bins, weights=np.full(len(same), 100 / len(same)), histtype="step",
            linewidth=2, color=sc.COLOR_ON_TIME,
            label=f"Same state (median {result['delivery_days_same_state']['median']} days)")
    ax.hist(diff, bins=bins, weights=np.full(len(diff), 100 / len(diff)), histtype="step",
            linewidth=2, color=sc.COLOR_LATE,
            label=f"Different state (median {result['delivery_days_different_state']['median']} days)")
    sc.style_axes(ax)
    ax.set_xlabel("Delivery time (days; values above 60 shown at 60)")
    ax.set_ylabel("Share of orders in group (%)")
    ax.set_title("Cross-state orders take longer to arrive", loc="left",
                 fontsize=12, color=sc.INK, pad=12)
    ax.legend(frameon=False, fontsize=9, labelcolor=sc.INK_SECONDARY)
    print("Figure:", sc.save_figure(fig, "03_delivery_days_by_distance_proxy"))


if __name__ == "__main__":
    main()
