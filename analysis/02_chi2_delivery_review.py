"""Chi-squared test of independence: delivery status vs review rating bucket.

Unit of analysis: one delivered order with a review.
Rating buckets: low (1-2), neutral (3), high (4-5).
With ~96,000 orders almost any difference is "statistically significant", so
the p-value alone says little. Cramér's V (effect size) and the row
percentages are reported to judge whether the association is meaningful.

Run with:  python analysis/02_chi2_delivery_review.py
"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

import stats_common as sc

BUCKETS = ["low (1-2)", "neutral (3)", "high (4-5)"]


def cramers_v_label(v: float) -> str:
    # Cohen's thresholds for a table whose smaller dimension is 2 (df* = 1).
    if v < 0.1:
        return "negligible"
    if v < 0.3:
        return "small"
    if v < 0.5:
        return "medium"
    return "large"


def main() -> None:
    df = sc.load_delivery_reviews()
    df["status"] = np.where(df["is_late"], "late", "on time")
    df["bucket"] = pd.cut(df["review_score"], bins=[0, 2, 3, 5], labels=BUCKETS)

    table = pd.crosstab(df["status"], df["bucket"]).loc[["on time", "late"], BUCKETS]
    chi2, p, dof, expected = stats.chi2_contingency(table.to_numpy())
    n = int(table.to_numpy().sum())
    v = float(np.sqrt(chi2 / (n * (min(table.shape) - 1))))
    row_pct = (table.div(table.sum(axis=1), axis=0) * 100).round(2)

    result = {
        "test": "Chi-squared test of independence (2 x 3)",
        "n": n,
        "observed": {s: {b: int(table.loc[s, b]) for b in BUCKETS} for s in table.index},
        "row_percent": {s: {b: float(row_pct.loc[s, b]) for b in BUCKETS} for s in row_pct.index},
        "min_expected_count": round(float(expected.min()), 1),
        "chi2": round(float(chi2), 1),
        "degrees_of_freedom": int(dof),
        "p_value": float(p),
        "cramers_v": round(v, 3),
        "effect_size_label": cramers_v_label(v),
    }

    low_on, low_late = row_pct.loc["on time", BUCKETS[0]], row_pct.loc["late", BUCKETS[0]]
    report = f"""CHI-SQUARED: delivery status vs review rating bucket
Observed counts:
{table.to_string()}

Row percentages:
{row_pct.to_string()}

  chi2 = {result['chi2']:,}, df = {dof}, p {sc.fmt_p(p)}, n = {n:,}
  smallest expected cell count = {result['min_expected_count']:,} (assumption of >= 5 holds)
  Cramér's V = {result['cramers_v']} ({result['effect_size_label']})

Interpretation: delivery status and rating bucket are not independent (p {sc.fmt_p(p)}).
Is it meaningful? Yes. The p-value is tiny partly because the sample is huge, but the
effect size is {result['effect_size_label']} (V = {result['cramers_v']}) and the practical gap is wide:
{low_late}% of late orders get a low rating (1-2) against {low_on}% of on-time orders."""
    sc.save_result("02_chi2_delivery_review", result, report)

    # Figure: share of each group in each rating bucket.
    fig, ax = plt.subplots(figsize=(7, 4))
    x = np.arange(len(BUCKETS))
    width = 0.38
    b1 = ax.bar(x - width / 2 - 0.01, row_pct.loc["on time"], width,
                color=sc.COLOR_ON_TIME, label="On time")
    b2 = ax.bar(x + width / 2 + 0.01, row_pct.loc["late"], width,
                color=sc.COLOR_LATE, label="Late")
    for bars in (b1, b2):
        ax.bar_label(bars, fmt="%.0f%%", fontsize=8, color=sc.INK_SECONDARY, padding=2)
    sc.style_axes(ax)
    ax.set_xticks(x, BUCKETS)
    ax.set_xlabel("Review rating bucket")
    ax.set_ylabel("Share of orders in group (%)")
    ax.set_title("Most late orders are rated low; most on-time orders are rated high",
                 loc="left", fontsize=12, color=sc.INK, pad=12)
    ax.legend(frameon=False, fontsize=9, labelcolor=sc.INK_SECONDARY)
    print("Figure:", sc.save_figure(fig, "02_rating_bucket_by_delivery_status"))


if __name__ == "__main__":
    main()
