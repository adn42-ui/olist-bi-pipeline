"""Step 1b: data-quality checks on the raw tables.

Every check is a SQL query that returns the number of violating rows.
A check passes when that number is 0. Every result is written to
logs/quality_checks.log. CRITICAL failures raise DataQualityError and stop
the pipeline; WARNING failures are logged and the pipeline continues.

Run on its own with:  python -m src.quality_checks
"""
import logging
from dataclasses import dataclass

import duckdb

from src import config

CRITICAL = "CRITICAL"
WARNING = "WARNING"


class DataQualityError(RuntimeError):
    """Raised when at least one CRITICAL check fails."""


@dataclass(frozen=True)
class Check:
    category: str  # null | duplicate_pk | orphan_fk | impossible_value
    name: str
    severity: str
    sql: str  # must return a single integer: the count of violating rows


def _null(table: str, column: str, severity: str, where: str = "TRUE") -> Check:
    suffix = "" if where == "TRUE" else f" [{where}]"
    return Check(
        "null",
        f"{table}.{column} is null{suffix}",
        severity,
        f"SELECT count(*) FROM raw.{table} WHERE {column} IS NULL AND ({where})",
    )


def _dup(table: str, key: str, severity: str) -> Check:
    return Check(
        "duplicate_pk",
        f"{table} duplicate key ({key})",
        severity,
        f"""SELECT coalesce(sum(n - 1), 0) FROM (
                SELECT count(*) AS n FROM raw.{table} GROUP BY {key} HAVING count(*) > 1
            )""",
    )


def _orphan(child: str, col: str, parent: str, parent_col: str, severity: str) -> Check:
    return Check(
        "orphan_fk",
        f"{child}.{col} has no match in {parent}.{parent_col}",
        severity,
        f"""SELECT count(*) FROM raw.{child} c
            WHERE c.{col} IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM raw.{parent} p WHERE p.{parent_col} = c.{col})""",
    )


def _impossible(name: str, table: str, condition: str, severity: str) -> Check:
    return Check(
        "impossible_value",
        name,
        severity,
        f"SELECT count(*) FROM raw.{table} WHERE {condition}",
    )


CHECKS: list[Check] = [
    # ---- nulls: keys and measures the star schema depends on are critical ----
    _null("orders", "order_id", CRITICAL),
    _null("orders", "customer_id", CRITICAL),
    _null("orders", "order_status", CRITICAL),
    _null("orders", "order_purchase_timestamp", CRITICAL),
    _null("orders", "order_estimated_delivery_date", CRITICAL),
    _null("order_items", "order_id", CRITICAL),
    _null("order_items", "order_item_id", CRITICAL),
    _null("order_items", "product_id", CRITICAL),
    _null("order_items", "seller_id", CRITICAL),
    _null("order_items", "price", CRITICAL),
    _null("order_items", "freight_value", CRITICAL),
    _null("customers", "customer_id", CRITICAL),
    _null("customers", "customer_unique_id", CRITICAL),
    _null("customers", "customer_state", CRITICAL),
    _null("products", "product_id", CRITICAL),
    _null("sellers", "seller_id", CRITICAL),
    _null("sellers", "seller_state", CRITICAL),
    _null("order_payments", "payment_value", CRITICAL),
    _null("order_reviews", "review_score", CRITICAL),
    # Descriptive attributes: analysis can tolerate gaps, so warn only.
    _null("orders", "order_delivered_customer_date", WARNING, "order_status = 'delivered'"),
    _null("orders", "order_approved_at", WARNING, "order_status = 'delivered'"),
    _null("products", "product_category_name", WARNING),
    _null("products", "product_weight_g", WARNING),
    # ---- duplicate primary keys ----
    _dup("orders", "order_id", CRITICAL),
    _dup("customers", "customer_id", CRITICAL),
    _dup("products", "product_id", CRITICAL),
    _dup("sellers", "seller_id", CRITICAL),
    _dup("order_items", "order_id, order_item_id", CRITICAL),
    _dup("order_payments", "order_id, payment_sequential", CRITICAL),
    _dup("category_translation", "product_category_name", CRITICAL),
    _dup("order_reviews", "review_id, order_id", CRITICAL),
    # review_id alone is not unique in the source (one review can cover
    # several orders), so this is tracked but does not stop the pipeline.
    _dup("order_reviews", "review_id", WARNING),
    # ---- orphaned foreign keys ----
    _orphan("orders", "customer_id", "customers", "customer_id", CRITICAL),
    _orphan("order_items", "order_id", "orders", "order_id", CRITICAL),
    _orphan("order_items", "product_id", "products", "product_id", CRITICAL),
    _orphan("order_items", "seller_id", "sellers", "seller_id", CRITICAL),
    _orphan("order_payments", "order_id", "orders", "order_id", CRITICAL),
    _orphan("order_reviews", "order_id", "orders", "order_id", CRITICAL),
    _orphan("products", "product_category_name", "category_translation",
            "product_category_name", WARNING),
    _orphan("orders", "order_id", "order_items", "order_id", WARNING),
    _orphan("orders", "order_id", "order_payments", "order_id", WARNING),
    # ---- impossible values ----
    _impossible("orders delivered to customer before purchase", "orders",
                "order_delivered_customer_date < order_purchase_timestamp", CRITICAL),
    _impossible("orders with estimated delivery before purchase", "orders",
                "order_estimated_delivery_date < order_purchase_timestamp", CRITICAL),
    _impossible("orders delivered to customer before carrier handoff", "orders",
                "order_delivered_customer_date < order_delivered_carrier_date", WARNING),
    _impossible("orders approved before purchase", "orders",
                "order_approved_at < order_purchase_timestamp", WARNING),
    _impossible("order_items with price <= 0", "order_items", "price <= 0", CRITICAL),
    _impossible("order_items with negative freight", "order_items",
                "freight_value < 0", CRITICAL),
    _impossible("order_reviews with score outside 1-5", "order_reviews",
                "review_score NOT BETWEEN 1 AND 5", CRITICAL),
    _impossible("order_payments with negative value", "order_payments",
                "payment_value < 0", CRITICAL),
    _impossible("order_payments with zero value", "order_payments",
                "payment_value = 0", WARNING),
    _impossible("order_payments with zero installments", "order_payments",
                "payment_installments < 1", WARNING),
    _impossible("products with weight <= 0 g", "products",
                "product_weight_g <= 0", WARNING),
]


def _get_logger() -> logging.Logger:
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("quality_checks")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fmt = logging.Formatter("%(asctime)s | %(message)s", "%Y-%m-%d %H:%M:%S")
    # mode="w": the log always describes the most recent run (idempotent).
    file_handler = logging.FileHandler(config.QUALITY_LOG, mode="w", encoding="utf-8")
    file_handler.setFormatter(fmt)
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("  %(message)s"))
    logger.addHandler(file_handler)
    logger.addHandler(console)
    return logger


def run_checks(con: duckdb.DuckDBPyConnection) -> list[dict]:
    """Run every check, log every result, raise DataQualityError on critical failures."""
    logger = _get_logger()
    results: list[dict] = []
    for check in CHECKS:
        violations = int(con.execute(check.sql).fetchone()[0])
        status = "PASS" if violations == 0 else ("FAIL" if check.severity == CRITICAL else "WARN")
        results.append({**check.__dict__, "violations": violations, "status": status})
        logger.info(
            "%-4s | %-8s | %-16s | %-62s | violations=%d",
            status, check.severity, check.category, check.name, violations,
        )

    n_pass = sum(r["status"] == "PASS" for r in results)
    n_warn = sum(r["status"] == "WARN" for r in results)
    failed = [r for r in results if r["status"] == "FAIL"]
    logger.info(
        "SUMMARY | %d checks | %d passed | %d warnings | %d critical failures",
        len(results), n_pass, n_warn, len(failed),
    )
    for handler in logger.handlers:
        handler.flush()

    if failed:
        detail = "\n".join(f"  - {r['name']}: {r['violations']:,} rows" for r in failed)
        raise DataQualityError(
            f"{len(failed)} critical data-quality check(s) failed:\n{detail}\n"
            f"See {config.QUALITY_LOG}"
        )
    return results


def main() -> None:
    with duckdb.connect(str(config.DB_PATH), read_only=True) as con:
        run_checks(con)


if __name__ == "__main__":
    main()
