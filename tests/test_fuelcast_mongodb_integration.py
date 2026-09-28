"""Opt-in live MongoDB smoke test; never touches the production collection."""

import csv
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from greenfleet.constants.fuelcast import (
    CANONICAL_COLUMNS, CANONICAL_FEATURES, CANONICAL_UNITS, DATASET_ID,
    EXPECTED_CONFIGS, SOURCE_TO_CANONICAL,
)
from greenfleet.database.fuelcast import run_fuelcast_mongodb
from greenfleet.pipeline.etl.fuelcast import _record_id


def _enabled():
    collection = os.getenv("MONGODB_INTEGRATION_COLLECTION", "")
    return (os.getenv("RUN_FUELCAST_MONGODB_INTEGRATION") == "1"
            and bool(os.getenv("MONGODB_URI"))
            and bool(os.getenv("MONGODB_INTEGRATION_DATABASE"))
            and collection.startswith("fuelcast_integration_")
            and collection != "fuelcast_telemetry")


@unittest.skipUnless(_enabled(), "requires explicit isolated MongoDB integration settings")
class FuelCastMongoIntegrationTests(unittest.TestCase):
    def test_three_vessels_first_and_repeated_load(self):
        revision = "1" * 40
        with tempfile.TemporaryDirectory() as root:
            run_dir = Path(root) / "fuelcast-integration-three-vessels"
            stage = run_dir / "02_etl"
            stage.mkdir(parents=True)
            rows = []
            for vessel in EXPECTED_CONFIGS:
                row = {"record_id": _record_id(revision, vessel, 1),
                       "dataset_version": revision, "vessel_id": vessel,
                       "time_index": 1, "fuel_consumption_kg_s": 0.5}
                row.update({name: 1.0 for name in CANONICAL_FEATURES})
                rows.append(row)
            csv_path = stage / "fuelcast_clean.csv"
            with csv_path.open("w", newline="") as stream:
                writer = csv.DictWriter(stream, CANONICAL_COLUMNS)
                writer.writeheader()
                writer.writerows(rows)
            audit = {"dataset_id": DATASET_ID, "source_run_id": run_dir.name,
                     "dataset_version": revision,
                     "canonical_sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
                     "canonical_columns": list(CANONICAL_COLUMNS),
                     "source_to_canonical": SOURCE_TO_CANONICAL, "units": CANONICAL_UNITS,
                     "per_vessel": {v: {"output_rows": 1} for v in EXPECTED_CONFIGS},
                     "totals": {"output_rows": 3}}
            (stage / "etl_audit.json").write_text(json.dumps(audit))
            options = {"database": os.environ["MONGODB_INTEGRATION_DATABASE"],
                       "collection": os.environ["MONGODB_INTEGRATION_COLLECTION"]}
            first = run_fuelcast_mongodb(run_dir, **options)
            self.assertEqual(first.verified_loaded_rows, 3)
            second = run_fuelcast_mongodb(run_dir, **options)
            self.assertEqual(second.verified_loaded_rows, 3)
            report = json.loads(second.report_path.read_text())
            self.assertEqual(report["batch_progress"]["upserted"], 0)
            self.assertEqual(report["batch_progress"]["modified"], 0)
            self.assertEqual(report["post_verification"]["indexes_to_create"], [])
            self.assertEqual(report["post_verification"]["active_version_per_vessel"],
                             {v: 1 for v in EXPECTED_CONFIGS})


if __name__ == "__main__":
    unittest.main()
