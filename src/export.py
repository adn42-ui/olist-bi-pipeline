"""Run saved SQL queries and export each result to a CSV in outputs/.

Every .sql file in sql/analysis/ and sql/dashboard/ holds exactly one query.
The CSV takes the query file's name: sql/analysis/01_x.sql -> outputs/01_x.csv.

Run on its own with:  python -m src.export
"""
from pathlib import Path

import duckdb

from src import config

QUERY_DIRS = [config.SQL_DIR / "analysis", config.SQL_DIR / "dashboard"]


def export_queries(con: duckdb.DuckDBPyConnection) -> list[Path]:
    """Run every saved query and write its result to outputs/. Returns the CSV paths."""
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for query_dir in QUERY_DIRS:
        for sql_file in sorted(query_dir.glob("*.sql")):
            df = con.execute(sql_file.read_text(encoding="utf-8")).df()
            if df.empty:
                raise RuntimeError(f"{sql_file} returned no rows")
            out = config.OUTPUT_DIR / f"{sql_file.stem}.csv"
            df.to_csv(out, index=False)
            written.append(out)
            print(f"  {sql_file.parent.name}/{sql_file.name:<40} -> outputs/{out.name} ({len(df):,} rows)")
    return written


def main() -> None:
    with duckdb.connect(str(config.DB_PATH), read_only=True) as con:
        export_queries(con)


if __name__ == "__main__":
    main()
