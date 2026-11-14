"""Single entry point for the Olist BI pipeline.

    python run_pipeline.py               # full run
    python run_pipeline.py --skip-stats  # skip the statistics scripts

Steps, in order:
  1. Ingest raw CSVs from data/raw/ into DuckDB
  2. Data-quality checks (stops the run on any critical failure)
  3. Build the star schema and reconcile it against the raw tables
  4. Export analysis and dashboard query results to outputs/
  5. Generate docs/dashboard.md
  6. Run the statistics scripts in analysis/

Idempotent: every run deletes the database and previous outputs and rebuilds
them from the raw CSVs, so rerunning always gives the same result.
"""
import argparse
import subprocess
import sys
import time

import duckdb

from src import build_schema, config, dashboard_spec, export, ingest, quality_checks

STATS_SCRIPTS = [
    "01_ttest_reviews.py",
    "02_chi2_delivery_review.py",
    "03_regression_delivery_time.py",
]


def clean() -> None:
    """Remove the database and all generated outputs so the run starts from nothing."""
    for path in (config.DB_PATH, config.DB_PATH.with_name(config.DB_PATH.name + ".wal")):
        path.unlink(missing_ok=True)
    for pattern in ("*.csv", "stats/*.json", "stats/*.txt", "figures/*.png"):
        for path in config.OUTPUT_DIR.glob(pattern):
            path.unlink()


def step(number: int, title: str) -> None:
    print(f"\n[{number}/6] {title}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Olist BI pipeline end to end.")
    parser.add_argument("--skip-stats", action="store_true",
                        help="skip the statistics scripts in analysis/")
    args = parser.parse_args()

    started = time.perf_counter()
    clean()
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    try:
        with duckdb.connect(str(config.DB_PATH)) as con:
            step(1, "Ingest raw CSVs")
            ingest.ingest(con)

            step(2, "Data-quality checks")
            results = quality_checks.run_checks(con)
            warnings = sum(r["status"] == "WARN" for r in results)
            print(f"  {len(results)} checks run, {warnings} warnings, 0 critical failures "
                  f"-> {config.QUALITY_LOG.relative_to(config.ROOT)}")

            step(3, "Build star schema")
            build_schema.build_schema(con)

            step(4, "Export analysis and dashboard queries")
            export.export_queries(con)

        step(5, "Generate dashboard specification")
        dashboard_spec.write_spec()

        step(6, "Statistics")
        if args.skip_stats:
            print("  skipped (--skip-stats)")
        else:
            # Run as separate processes, after the connection above is closed,
            # so each script can also be run on its own.
            for script in STATS_SCRIPTS:
                print(f"\n  --- analysis/{script} ---")
                subprocess.run(
                    [sys.executable, str(config.ROOT / "analysis" / script)], check=True
                )
    except quality_checks.DataQualityError as exc:
        print(f"\nPIPELINE STOPPED: data-quality failure\n{exc}", file=sys.stderr)
        return 1
    except (FileNotFoundError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"\nPIPELINE FAILED: {exc}", file=sys.stderr)
        return 1

    print(f"\nPipeline finished in {time.perf_counter() - started:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
