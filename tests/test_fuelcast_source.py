"""Offline contract tests for the pinned FuelCast source stage."""

import csv
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from datasets import Dataset, Features, Value

from greenfleet.constants.fuelcast import DATASET_ID, EXPECTED_CONFIGS, RAW_COLUMNS
from greenfleet.data_sources.fuelcast import ingest_fuelcast


SHA = "a" * 40
SOURCE_FIELDS = (
    "index",
    "Ship_SpeedOverGround",
    "Weather_WindSpeed10M",
    "Weather_WindDirection10M",
    "Weather_WaveHeight",
    "Weather_WavePeriod",
    "Weather_OceanCurrentVelocity",
    "Consumer_Total_MomentaryFuel",
)


def fixture(*, missing=None, bad_type=None, offset=0):
    fields = {name: Value("int64" if name == "index" else "float64") for name in SOURCE_FIELDS}
    if missing:
        del fields[missing]
    if bad_type:
        fields[bad_type] = Value("string")
    values = {
        name: ([offset, offset + 1] if name == "index" else [1.0, None])
        for name in fields
    }
    if bad_type:
        values[bad_type] = ["bad", None]
    return Dataset.from_dict(values, features=Features(fields))


class FuelCastSourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.run_dir = Path(self.tmp.name) / "artifacts" / "test-run"
        self.datasets = {name: fixture(offset=i * 10) for i, name in enumerate(EXPECTED_CONFIGS)}
        self.info_patch = patch(
            "greenfleet.data_sources.fuelcast.HfApi.dataset_info",
            return_value=SimpleNamespace(sha=SHA),
        )
        self.config_patch = patch(
            "greenfleet.data_sources.fuelcast.get_dataset_config_names",
            return_value=[*EXPECTED_CONFIGS, "extra_config"],
        )
        self.load_patch = patch(
            "greenfleet.data_sources.fuelcast.load_dataset",
            side_effect=lambda dataset_id, name, **kwargs: self.datasets[name],
        )
        self.now_patch = patch(
            "greenfleet.data_sources.fuelcast._utc_now",
            return_value=datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc),
        )
        self.info = self.info_patch.start()
        self.configs = self.config_patch.start()
        self.loader = self.load_patch.start()
        self.now = self.now_patch.start()
        for item in (self.info_patch, self.config_patch, self.load_patch, self.now_patch):
            self.addCleanup(item.stop)

    def test_snapshot_manifest_and_revision_are_stable(self):
        artifact = ingest_fuelcast(self.run_dir, revision="main")
        self.info.assert_called_once_with(DATASET_ID, revision="main")
        self.configs.assert_called_once_with(DATASET_ID, revision=SHA)
        self.assertEqual(
            self.loader.call_args_list,
            [
                unittest.mock.call(DATASET_ID, name, split="train", revision=SHA)
                for name in EXPECTED_CONFIGS
            ],
        )
        self.assertEqual(artifact.dataset_version, SHA)
        self.assertEqual(artifact.row_counts, dict.fromkeys(EXPECTED_CONFIGS, 2))
        self.assertEqual(artifact.total_rows, 6)

        with artifact.snapshot_path.open(newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(list(rows[0]), list(RAW_COLUMNS))
        self.assertEqual([row["vessel_id"] for row in rows], [name for name in EXPECTED_CONFIGS for _ in range(2)])
        self.assertEqual([row["time_index"] for row in rows], ["0", "1", "10", "11", "20", "21"])
        self.assertEqual(rows[1]["Weather_WaveHeight"], "")
        self.assertEqual(rows[1]["Consumer_Total_MomentaryFuel"], "")

        manifest = json.loads(artifact.manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["dataset_id"], DATASET_ID)
        self.assertEqual(manifest["dataset_version"], SHA)
        self.assertEqual(manifest["retrieved_at_utc"], "2026-09-28T12:00:00+00:00")
        self.assertEqual(manifest["license"], "CC BY-NC-ND 4.0")
        self.assertEqual(manifest["available_configurations"], [*EXPECTED_CONFIGS, "extra_config"])
        self.assertEqual(manifest["loaded_configurations"], list(EXPECTED_CONFIGS))
        self.assertEqual(manifest["total_rows"], 6)
        self.assertEqual(manifest["raw_columns"], list(RAW_COLUMNS))
        self.assertEqual(manifest["snapshot_sha256"], hashlib.sha256(artifact.snapshot_path.read_bytes()).hexdigest())
        expected_pairs = [[name, "int64" if name == "index" else "double"] for name in SOURCE_FIELDS]
        expected_hash = hashlib.sha256(json.dumps(expected_pairs, separators=(",", ":")).encode()).hexdigest()
        self.assertEqual(manifest["schema_fingerprints"], dict.fromkeys(EXPECTED_CONFIGS, expected_hash))
        combined = [[name, expected_pairs] for name in EXPECTED_CONFIGS]
        combined_hash = hashlib.sha256(json.dumps(combined, separators=(",", ":")).encode()).hexdigest()
        self.assertEqual(manifest["combined_schema_fingerprint"], combined_hash)

    def test_missing_configuration_does_not_publish(self):
        self.configs.return_value = ["cps_poseidon", "cps_triton"]
        with self.assertRaisesRegex(RuntimeError, "oss_ceto"):
            ingest_fuelcast(self.run_dir)
        self.loader.assert_not_called()
        self.assertFalse(self.run_dir.exists())

    def test_exact_column_case_is_required_and_failure_is_atomic(self):
        self.datasets["oss_ceto"] = fixture(missing="Weather_WindSpeed10M")
        with self.assertRaisesRegex(ValueError, "Weather_WindSpeed10M"):
            ingest_fuelcast(self.run_dir)
        self.assertFalse(self.run_dir.exists())
        self.assertEqual(list(self.run_dir.parent.glob(".test-run.source-*")), [])

    def test_declared_types_are_checked(self):
        for field in ("index", "Consumer_Total_MomentaryFuel", "Weather_WavePeriod"):
            with self.subTest(field=field):
                self.datasets["cps_triton"] = fixture(bad_type=field)
                with self.assertRaisesRegex(ValueError, field):
                    ingest_fuelcast(self.run_dir)
                self.assertFalse(self.run_dir.exists())

    def test_existing_run_is_refused_before_hub_call(self):
        self.run_dir.mkdir(parents=True)
        with self.assertRaises(FileExistsError):
            ingest_fuelcast(self.run_dir)
        self.info.assert_not_called()


if __name__ == "__main__":
    unittest.main()
