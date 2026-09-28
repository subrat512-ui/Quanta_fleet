"""Offline contract tests for shared FuelCast model partitions."""

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import joblib
import numpy as np
import pandas as pd

from greenfleet.constants.fuelcast import (
    CANONICAL_COLUMNS, CANONICAL_UNITS, DATASET_ID, EXPECTED_CONFIGS,
)
from greenfleet.ml_pipeline.transformation.fuelcast import (
    FuelCastImputer, load_fuelcast_partitions, run_fuelcast_transformation,
)


VERSION = "a" * 40


def make_run(root: Path, n: int = 20, *, future: float = 10.0) -> Path:
    run = root / "synthetic-run"
    etl = run / "02_etl"
    etl.mkdir(parents=True)
    rows = []
    for vessel in EXPECTED_CONFIGS:
        for index in range(n):
            rows.append({
                "record_id": hashlib.sha256(f"{vessel}-{index}".encode()).hexdigest(),
                "dataset_version": VERSION, "vessel_id": vessel,
                "time_index": index, "speed_over_ground": None if index == 0 else (future if index >= 14 else 2.0),
                "wind_speed": float(index), "wind_direction": (0, 90, 360)[index % 3],
                "wave_height": 1.0, "wave_period": 5.0,
                "current_speed": 0.3, "fuel_consumption_kg_s": float(index + 1),
            })
    canonical = etl / "fuelcast_clean.csv"
    pd.DataFrame(rows, columns=CANONICAL_COLUMNS).to_csv(canonical, index=False)
    audit = {
        "dataset_id": DATASET_ID, "source_run_id": run.name,
        "dataset_version": VERSION, "canonical_sha256": hashlib.sha256(canonical.read_bytes()).hexdigest(),
        "canonical_columns": list(CANONICAL_COLUMNS), "units": CANONICAL_UNITS,
        "per_vessel": {name: {"output_rows": n} for name in EXPECTED_CONFIGS},
        "totals": {"output_rows": 3 * n},
    }
    (etl / "etl_audit.json").write_text(json.dumps(audit), encoding="utf-8")
    return run


class FuelCastTransformationTests(unittest.TestCase):
    def test_split_and_reload(self):
        with tempfile.TemporaryDirectory() as temp:
            run = make_run(Path(temp))
            artifact = run_fuelcast_transformation(run)
            arrays, schema = load_fuelcast_partitions(run)
            self.assertEqual(schema["target"], "fuel_consumption_kg_s")
            self.assertEqual([len(arrays[name]["target"]) for name in ("train", "validation", "test")], [42, 9, 9])
            self.assertEqual(arrays["train"]["features"].shape, (42, 7))
            self.assertEqual(arrays["train"]["vqr_features"].shape, (42, 6))
            manifest = json.loads(artifact.split_manifest_path.read_text())
            for vessel in EXPECTED_CONFIGS:
                parts = manifest["per_vessel"][vessel]
                self.assertEqual([parts[name]["count"] for name in ("train", "validation", "test")], [14, 3, 3])
                self.assertLess(parts["train"]["last_time_index"], parts["validation"]["first_time_index"])
                self.assertLess(parts["validation"]["last_time_index"], parts["test"]["first_time_index"])
            self.assertEqual(len(set(np.concatenate([arrays[name]["record_id"] for name in arrays]))), 60)
            scaler = joblib.load(artifact.vqr_target_scaler_path)
            np.testing.assert_allclose(scaler.inverse_transform(arrays["test"]["vqr_target"].reshape(-1, 1)).ravel(), arrays["test"]["target"])
            with self.assertRaises(FileExistsError):
                run_fuelcast_transformation(run)

    def test_no_validation_or_test_fit(self):
        with tempfile.TemporaryDirectory() as temp:
            first = make_run(Path(temp) / "first", future=10.0)
            second = make_run(Path(temp) / "second", future=10000.0)
            a = run_fuelcast_transformation(first)
            b = run_fuelcast_transformation(second)
            np.testing.assert_allclose(joblib.load(a.preprocessor_path)["scaler"].mean_,
                                       joblib.load(b.preprocessor_path)["scaler"].mean_)
            np.testing.assert_allclose(joblib.load(a.vqr_preprocessor_path)["angle"].scaler_.data_max_,
                                       joblib.load(b.vqr_preprocessor_path)["angle"].scaler_.data_max_)
            np.testing.assert_allclose(joblib.load(a.vqr_target_scaler_path).data_max_,
                                       joblib.load(b.vqr_target_scaler_path).data_max_)
            np.testing.assert_allclose(load_fuelcast_partitions(first)[0]["train"]["features"],
                                       load_fuelcast_partitions(second)[0]["train"]["features"])

    def test_circular_direction_and_fresh_process(self):
        with tempfile.TemporaryDirectory() as temp:
            run = make_run(Path(temp))
            artifact = run_fuelcast_transformation(run)
            classical = joblib.load(artifact.preprocessor_path)
            input_rows = np.array([[2, 1, angle, 1, 5, 0.3] for angle in (0, 90, 360)], dtype=float)
            encoded = classical["direction"].transform(classical["imputer"].transform(input_rows))
            np.testing.assert_allclose(encoded[:, 2:4], [[0, 1], [1, 0], [0, 1]], atol=1e-14)
            result = subprocess.run([sys.executable, "-c",
                "import joblib,sys; p=joblib.load(sys.argv[1]); print(p.transform([[2,1,90,1,5,.3]]).shape)",
                str(artifact.preprocessor_path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("(1, 7)", result.stdout)

    def test_missing_wind_wraparound_uses_training_circular_value(self):
        values = np.array([
            [2, 1, 0, 1, 5, .3],
            [2, 1, 360, 1, 5, .3],
            [np.nan, 1, np.nan, 1, 5, .3],
        ])
        imputer = FuelCastImputer().fit(values[:2])
        filled = imputer.transform(values)
        self.assertAlmostEqual(filled[2, 0], 2.0)
        self.assertLess(min(abs(filled[2, 2]), abs(filled[2, 2] - 360)), 1e-10)

    def test_loader_rejects_vessel_time_mismatch_even_with_updated_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            run = make_run(Path(temp))
            artifact = run_fuelcast_transformation(run)
            with np.load(artifact.train_path, allow_pickle=False) as content:
                arrays = {key: content[key] for key in content.files}
            arrays["vessel_id"][0] = "oss_ceto"
            np.savez_compressed(artifact.train_path, **arrays)
            manifest = json.loads(artifact.split_manifest_path.read_text())
            manifest["artifact_sha256"]["train.npz"] = hashlib.sha256(artifact.train_path.read_bytes()).hexdigest()
            artifact.split_manifest_path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "vessel/time metadata mismatch"):
                load_fuelcast_partitions(run)

    def test_rejects_changed_input_and_output(self):
        with tempfile.TemporaryDirectory() as temp:
            run = make_run(Path(temp))
            canonical = run / "02_etl" / "fuelcast_clean.csv"
            canonical.write_bytes(canonical.read_bytes() + b"\n")
            with self.assertRaisesRegex(ValueError, "audit mismatch"):
                run_fuelcast_transformation(run)
            self.assertFalse((run / "04_transformation").exists())
        with tempfile.TemporaryDirectory() as temp:
            run = make_run(Path(temp))
            artifact = run_fuelcast_transformation(run)
            artifact.train_path.write_bytes(artifact.train_path.read_bytes() + b"x")
            with self.assertRaisesRegex(ValueError, "artifact changed"):
                load_fuelcast_partitions(run)

    def test_small_vessel_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            run = make_run(Path(temp), n=3)
            with self.assertRaisesRegex(ValueError, "cannot populate"):
                run_fuelcast_transformation(run)

    def test_time_index_above_float_precision_remains_exact(self):
        with tempfile.TemporaryDirectory() as temp:
            run = make_run(Path(temp))
            canonical = run / "02_etl" / "fuelcast_clean.csv"
            frame = pd.read_csv(canonical)
            frame.loc[0, "time_index"] = 9007199254740993
            frame.to_csv(canonical, index=False)
            audit_path = run / "02_etl" / "etl_audit.json"
            audit = json.loads(audit_path.read_text())
            audit["canonical_sha256"] = hashlib.sha256(canonical.read_bytes()).hexdigest()
            audit_path.write_text(json.dumps(audit))
            run_fuelcast_transformation(run)
            arrays, _ = load_fuelcast_partitions(run)
            times = np.concatenate([arrays[name]["time_index"] for name in ("train", "validation", "test")])
            self.assertIn(9007199254740993, times)

    def test_failed_publication_cleans_staging_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            run = make_run(Path(temp))
            with patch("greenfleet.ml_pipeline.transformation.fuelcast.os.symlink", side_effect=FileExistsError("race")):
                with self.assertRaisesRegex(FileExistsError, "race"):
                    run_fuelcast_transformation(run)
            self.assertFalse((run / "04_transformation").exists())
            self.assertEqual(list(run.glob(".04_transformation-data-*")), [])


if __name__ == "__main__":
    unittest.main()
