"""Step 1a: load every raw Olist CSV into the `raw` schema of a DuckDB database.

Run on its own with:  python -m src.ingest
"""
import duckdb

from src import config


def ingest(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """Load all raw CSVs. Returns {table_name: row_count}. Fails if any file is missing."""
    missing = [
        fname
        for fname, _ in config.RAW_TABLES.values()
        if not (config.RAW_DIR / fname).exists()
    ]
    if missing:
        raise FileNotFoundError(
            f"Missing raw CSV(s) in {config.RAW_DIR}: " + ", ".join(missing)
        )

    con.execute("CREATE SCHEMA IF NOT EXISTS raw")
    counts: dict[str, int] = {}
    for table, (fname, type_overrides) in config.RAW_TABLES.items():
        path = (config.RAW_DIR / fname).as_posix()
        # sample_size=-1 scans the whole file so type inference is not fooled
        # by the first rows (e.g. free-text review comments).
        # Overrides come from config.py (trusted), so they are inlined as a literal.
        types_clause = ""
        if type_overrides:
            pairs = ", ".join(f"'{col}': '{typ}'" for col, typ in type_overrides.items())
            types_clause = f", types = {{{pairs}}}"
        con.execute(
            f"""
            CREATE OR REPLACE TABLE raw.{table} AS
            SELECT * FROM read_csv(?, header = true, sample_size = -1{types_clause})
            """,
            [path],
        )
        counts[table] = con.execute(f"SELECT count(*) FROM raw.{table}").fetchone()[0]
        print(f"  raw.{table:<22} {counts[table]:>9,} rows  <- {fname}")
    return counts


def main() -> None:
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(config.DB_PATH)) as con:
        print("Ingesting raw CSVs into", config.DB_PATH)
        ingest(con)


if __name__ == "__main__":
    main()
