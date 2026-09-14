"""Command-line runner for ``python -m greenfleet.pipeline.etl``."""

import argparse
import json

from greenfleet.pipeline.etl.pipeline import run_etl


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the GreenFleet ETL pipeline.")
    parser.add_argument("source", help="Input CSV file")
    parser.add_argument("output", help="Output CSV or Parquet file")
    parser.add_argument("--audit", help="Optional JSON audit-report path")
    arguments = parser.parse_args()

    result = run_etl(arguments.source, arguments.output, audit_path=arguments.audit)
    print(json.dumps(result.to_dict(), indent=2))


if __name__ == "__main__":
    main()
