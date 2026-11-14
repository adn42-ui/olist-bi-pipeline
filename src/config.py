"""Central paths and table definitions for the Olist pipeline."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

RAW_DIR = ROOT / "data" / "raw"
DB_PATH = ROOT / "data" / "olist.duckdb"
SQL_DIR = ROOT / "sql"
OUTPUT_DIR = ROOT / "outputs"
LOG_DIR = ROOT / "logs"
QUALITY_LOG = LOG_DIR / "quality_checks.log"

# raw table name -> (CSV file name, column type overrides)
# Zip-code prefixes are forced to VARCHAR so leading zeros survive.
RAW_TABLES: dict[str, tuple[str, dict[str, str]]] = {
    "customers": (
        "olist_customers_dataset.csv",
        {"customer_zip_code_prefix": "VARCHAR"},
    ),
    "geolocation": (
        "olist_geolocation_dataset.csv",
        {"geolocation_zip_code_prefix": "VARCHAR"},
    ),
    "order_items": ("olist_order_items_dataset.csv", {}),
    "order_payments": ("olist_order_payments_dataset.csv", {}),
    "order_reviews": ("olist_order_reviews_dataset.csv", {}),
    "orders": ("olist_orders_dataset.csv", {}),
    "products": ("olist_products_dataset.csv", {}),
    "sellers": (
        "olist_sellers_dataset.csv",
        {"seller_zip_code_prefix": "VARCHAR"},
    ),
    "category_translation": ("product_category_name_translation.csv", {}),
}
