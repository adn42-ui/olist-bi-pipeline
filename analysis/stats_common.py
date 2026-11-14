"""Shared helpers for the statistics scripts: data access, result files, chart style."""
import json
import sys
from pathlib import Path

import duckdb
import matplotlib

matplotlib.use("Agg")  # render to files; no display needed
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import config  # noqa: E402

STATS_DIR = config.OUTPUT_DIR / "stats"
FIG_DIR = config.OUTPUT_DIR / "figures"

# Chart colours: a fixed, colour-blind-safe pair. Colour follows the group,
# so "on time" is always blue and "late" is always orange in every figure.
COLOR_ON_TIME = "#2a78d6"
COLOR_LATE = "#eb6834"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
SURFACE = "#fcfcfb"


def query(sql: str) -> pd.DataFrame:
    """Run a query against the pipeline database and return a DataFrame."""
    with duckdb.connect(str(config.DB_PATH), read_only=True) as con:
        return con.execute(sql).df()


def load_delivery_reviews() -> pd.DataFrame:
    """One row per delivered order that has a review: is_late, review_score, delivery_days."""
    return query(
        """
        SELECT o.order_id, o.is_late, o.delivery_days, r.review_score
        FROM v_orders o
        JOIN v_order_reviews r ON r.order_id = o.order_id
        WHERE o.is_late IS NOT NULL
        """
    )


def fmt_p(p: float) -> str:
    """Format a p-value; values too small for a float to hold print as a bound, not 0."""
    return "< 1e-300" if p < 1e-300 else f"= {p:.3g}"


def save_result(name: str, result: dict, report: str) -> None:
    """Write machine-readable (JSON) and human-readable (TXT) results, and print the report."""
    STATS_DIR.mkdir(parents=True, exist_ok=True)
    (STATS_DIR / f"{name}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (STATS_DIR / f"{name}.txt").write_text(report + "\n", encoding="utf-8")
    print(report)


def style_axes(ax) -> None:
    """Quiet axes: no box, hairline horizontal grid, muted ticks."""
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(AXIS)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(colors=INK_SECONDARY, length=0, labelsize=9)
    ax.xaxis.label.set_color(INK_SECONDARY)
    ax.yaxis.label.set_color(INK_SECONDARY)


def save_figure(fig, name: str) -> Path:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    path = FIG_DIR / f"{name}.png"
    fig.patch.set_facecolor(SURFACE)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path
