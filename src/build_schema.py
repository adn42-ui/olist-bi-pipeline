"""Step 2: build the star schema from sql/schema.sql and verify it reconciles
with the raw tables.

Run on its own with:  python -m src.build_schema
"""
import duckdb

from src import config

SCHEMA_SQL = config.SQL_DIR / "schema.sql"

# (description, query returning one value, query returning the expected value)
RECONCILIATIONS = [
    (
        "fact_order_items row count equals raw.order_items",
        "SELECT count(*) FROM fact_order_items",
        "SELECT count(*) FROM raw.order_items",
    ),
    (
        "fact_order_items revenue equals raw price + freight",
        "SELECT round(sum(total_value), 2) FROM fact_order_items",
        "SELECT round(sum(price + freight_value), 2) FROM raw.order_items",
    ),
    (
        "dim_customer has one row per customer_unique_id",
        "SELECT count(*) FROM dim_customer",
        "SELECT count(DISTINCT customer_unique_id) FROM raw.customers",
    ),
    (
        "dim_product row count equals raw.products",
        "SELECT count(*) FROM dim_product",
        "SELECT count(*) FROM raw.products",
    ),
    (
        "dim_seller row count equals raw.sellers",
        "SELECT count(*) FROM dim_seller",
        "SELECT count(*) FROM raw.sellers",
    ),
    (
        "v_orders has one row per order that has items",
        "SELECT count(*) FROM v_orders",
        "SELECT count(DISTINCT order_id) FROM raw.order_items",
    ),
    (
        "v_order_reviews has one row per reviewed order",
        "SELECT count(*) FROM v_order_reviews",
        "SELECT count(DISTINCT order_id) FROM raw.order_reviews",
    ),
    (
        "dim_date has no gaps between its first and last day",
        "SELECT count(*) FROM dim_date",
        "SELECT date_diff('day', min(full_date), max(full_date)) + 1 FROM dim_date",
    ),
]


def build_schema(con: duckdb.DuckDBPyConnection) -> None:
    """Execute schema.sql, then fail loudly if the result does not reconcile."""
    con.execute(SCHEMA_SQL.read_text(encoding="utf-8"))

    for table in [
        "dim_date", "dim_customer", "dim_product", "dim_seller",
        "fact_order_items", "fact_order_payments", "fact_order_reviews",
    ]:
        n = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        print(f"  {table:<22} {n:>9,} rows")

    failures = []
    for description, actual_sql, expected_sql in RECONCILIATIONS:
        actual = con.execute(actual_sql).fetchone()[0]
        expected = con.execute(expected_sql).fetchone()[0]
        ok = actual == expected
        print(f"  {'OK  ' if ok else 'FAIL'} {description}: {actual:,} vs {expected:,}")
        if not ok:
            failures.append(description)
    if failures:
        raise RuntimeError("Star schema failed reconciliation: " + "; ".join(failures))


def main() -> None:
    with duckdb.connect(str(config.DB_PATH)) as con:
        print("Building star schema in", config.DB_PATH)
        build_schema(con)


if __name__ == "__main__":
    main()
