"""Two-sample t-test: do late deliveries get lower review scores than on-time ones?

Unit of analysis: one delivered order with a review.
Test: Welch's t-test (does not assume equal variances; the groups differ
greatly in size and spread). Effect size: Cohen's d with a pooled SD.
Review scores are ordinal (1-5) and skewed, so a Mann-Whitney U test is
reported as a robustness check.

Run with:  python analysis/01_ttest_reviews.py
"""
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

import stats_common as sc


def cohen_d_label(d: float) -> str:
    d = abs(d)
    if d < 0.2:
        return "negligible"
    if d < 0.5:
        return "small"
    if d < 0.8:
        return "medium"
    return "large"


def main() -> None:
    df = sc.load_delivery_reviews()
    on_time = df.loc[~df["is_late"], "review_score"].to_numpy(dtype=float)
    late = df.loc[df["is_late"], "review_score"].to_numpy(dtype=float)

    t = stats.ttest_ind(on_time, late, equal_var=False)
    ci = t.confidence_interval(0.95)
    diff = on_time.mean() - late.mean()
    pooled_sd = np.sqrt(
        ((len(on_time) - 1) * on_time.var(ddof=1) + (len(late) - 1) * late.var(ddof=1))
        / (len(on_time) + len(late) - 2)
    )
    d = diff / pooled_sd
    mwu = stats.mannwhitneyu(on_time, late, alternative="two-sided")

    result = {
        "test": "Welch two-sample t-test",
        "n_on_time": int(len(on_time)),
        "n_late": int(len(late)),
        "mean_on_time": round(float(on_time.mean()), 3),
        "mean_late": round(float(late.mean()), 3),
        "sd_on_time": round(float(on_time.std(ddof=1)), 3),
        "sd_late": round(float(late.std(ddof=1)), 3),
        "mean_difference": round(float(diff), 3),
        "ci95_difference": [round(float(ci.low), 3), round(float(ci.high), 3)],
        "t_statistic": round(float(t.statistic), 2),
        "degrees_of_freedom": round(float(t.df), 1),
        "p_value": float(t.pvalue),
        "cohens_d": round(float(d), 3),
        "effect_size_label": cohen_d_label(d),
        "mann_whitney_u_p_value": float(mwu.pvalue),
        "pct_one_star_on_time": round(float((on_time == 1).mean() * 100), 2),
        "pct_one_star_late": round(float((late == 1).mean() * 100), 2),
    }

    report = f"""T-TEST: review score, on-time vs late deliveries
  on time : n = {result['n_on_time']:,}  mean = {result['mean_on_time']}  sd = {result['sd_on_time']}
  late    : n = {result['n_late']:,}  mean = {result['mean_late']}  sd = {result['sd_late']}
  mean difference (on time - late) = {result['mean_difference']}  95% CI {result['ci95_difference']}
  Welch t = {result['t_statistic']}, df = {result['degrees_of_freedom']}, p {sc.fmt_p(result['p_value'])}
  Cohen's d = {result['cohens_d']} ({result['effect_size_label']})
  Mann-Whitney U p {sc.fmt_p(result['mann_whitney_u_p_value'])} (robustness check for ordinal data)
  1-star share: on time {result['pct_one_star_on_time']}%, late {result['pct_one_star_late']}%

Interpretation: orders delivered late are rated {result['mean_difference']} points lower on the
5-point scale than orders delivered on time ({result['mean_late']} vs {result['mean_on_time']}).
The difference is statistically significant and the effect is {result['effect_size_label']}
(d = {result['cohens_d']}), so it is a practically important gap, not just an artefact of the
large sample. This is an association: it does not prove lateness alone causes the low score."""
    sc.save_result("01_ttest_reviews", result, report)

    # Figure: score distribution within each group.
    scores = np.arange(1, 6)
    share_on = [(on_time == s).mean() * 100 for s in scores]
    share_late = [(late == s).mean() * 100 for s in scores]
    fig, ax = plt.subplots(figsize=(7, 4))
    width = 0.38
    bars_on = ax.bar(scores - width / 2 - 0.01, share_on, width, color=sc.COLOR_ON_TIME,
                     label=f"On time (mean {result['mean_on_time']})")
    bars_late = ax.bar(scores + width / 2 + 0.01, share_late, width, color=sc.COLOR_LATE,
                       label=f"Late (mean {result['mean_late']})")
    for bars in (bars_on, bars_late):
        ax.bar_label(bars, fmt="%.0f%%", fontsize=8, color=sc.INK_SECONDARY, padding=2)
    sc.style_axes(ax)
    ax.set_xticks(scores)
    ax.set_xlabel("Review score")
    ax.set_ylabel("Share of orders in group (%)")
    ax.set_title("Late deliveries get far more 1-star reviews", loc="left",
                 fontsize=12, color=sc.INK, pad=12)
    ax.legend(frameon=False, fontsize=9, labelcolor=sc.INK_SECONDARY)
    print("Figure:", sc.save_figure(fig, "01_review_score_by_delivery_status"))


if __name__ == "__main__":
    main()
