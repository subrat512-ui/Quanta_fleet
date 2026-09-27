"""Command-line entry point for the standalone FuelCast source stage."""

import argparse
import re

from greenfleet.constants.training_pipeline_constants import ARTIFACTS_DIR
from greenfleet.data_sources.fuelcast import ingest_fuelcast


def main() -> None:
    parser = argparse.ArgumentParser(description="Download a pinned FuelCast raw snapshot")
    parser.add_argument("--run-id", required=True, help="New artifacts run directory name")
    parser.add_argument("--revision", help="Optional Hub commit, tag, or branch to resolve")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", args.run_id) or args.run_id in {".", ".."}:
        parser.error("--run-id must be a single safe directory name")
    artifact = ingest_fuelcast(ARTIFACTS_DIR / args.run_id, revision=args.revision)
    print(f"FuelCast source snapshot: {artifact.snapshot_path}")
    print(f"Dataset version: {artifact.dataset_version}")
    print(f"Rows: {artifact.row_counts} (total {artifact.total_rows})")


if __name__ == "__main__":
    main()
