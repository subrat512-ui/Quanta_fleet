"""Synthetic Phase 7 tests; no downloaded data or test partition is opened."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import joblib
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from greenfleet.config.fuelcast_vqr_config import FuelCastVQRConfig
from greenfleet.constants.fuelcast import DATASET_ID, EXPECTED_CONFIGS
from greenfleet.constants.fuelcast_vqr import VQR_FEATURES, VQR_MODES
from greenfleet.ml_pipeline.quantum.fuelcast_vqr import (
    sample_training, train_vqr, verify_candidate,
)
from greenfleet.ml_pipeline.quantum.fuelcast_vqr_data import load_saved_vqr_validation
from greenfleet.ml_pipeline.quantum.fuelcast_vqr_model import (
    build_vqr_circuits, load_vqr_candidate, quantum_dependencies,
)
from greenfleet.ml_pipeline.training.fuelcast_data import sha256_file
from greenfleet.ml_pipeline.transformation.fuelcast import FuelCastImputer, VQRAngleEncoder

QUANTUM_SMOKE = (os.environ.get("GREENFLEET_RUN_QUANTUM_SMOKE") == "1"
                 and __import__("importlib").util.find_spec("qiskit_machine_learning") is not None)


def synthetic_vqr_run(root: Path) -> tuple[Path, str, str]:
    run = root / "synthetic-vqr-run"
    etl = run / "02_etl"
    stage = run / "04_transformation"
    etl.mkdir(parents=True)
    stage.mkdir()
    version = "a" * 40
    canonical = etl / "fuelcast_clean.csv"
    canonical.write_text("invented fixture only\n", encoding="utf-8")
    canonical_hash = sha256_file(canonical)
    data = {}
    details = {v: {} for v in EXPECTED_CONFIGS}
    for name, start, stop in (("train", 0, 10), ("validation", 10, 14)):
        x, y, ids, vessels, times = [], [], [], [], []
        for vessel_number, vessel in enumerate(EXPECTED_CONFIGS):
            vessel_ids = []
            for index in range(start, stop):
                x.append([2 + 0.1 * index + vessel_number,
                          1 + 0.2 * (index % 4), (index * 31) % 360,
                          0.4 + 0.03 * index, 3 + 0.1 * index,
                          0.2 + 0.05 * vessel_number])
                y.append(0.3 + 0.02 * index + 0.03 * vessel_number)
                identity = f"{vessel}-{index}"
                ids.append(identity)
                vessel_ids.append(identity)
                vessels.append(vessel)
                times.append(index)
            details[vessel][name] = {
                "count": stop - start, "first_time_index": start,
                "last_time_index": stop - 1, "record_ids": vessel_ids,
            }
        data[name] = (np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64),
                      np.asarray(ids), np.asarray(vessels), np.asarray(times, dtype=np.int64))
    raw_train, y_train, *_ = data["train"]
    angle = Pipeline([("imputer", FuelCastImputer()), ("angle", VQRAngleEncoder())])
    angle.fit(raw_train)
    target_scaler = MinMaxScaler(feature_range=(-1, 1)).fit(y_train.reshape(-1, 1))
    joblib.dump(angle, stage / "vqr_preprocessor.pkl")
    joblib.dump(target_scaler, stage / "vqr_target_scaler.pkl")
    for name, (raw, target, ids, vessels, times) in data.items():
        np.savez_compressed(
            stage / f"{name}.npz", features=np.zeros((len(target), 7)),
            vqr_features=angle.transform(raw), target=target,
            vqr_target=target_scaler.transform(target.reshape(-1, 1)).reshape(-1),
            record_id=ids, vessel_id=vessels, time_index=times,
        )
    for vessel in EXPECTED_CONFIGS:
        details[vessel]["test"] = {"count": 1, "first_time_index": 14,
                                   "last_time_index": 14, "record_ids": [f"{vessel}-14"]}
    schema = {"dataset_id": DATASET_ID, "dataset_version": version,
              "raw_features": list(VQR_FEATURES), "vqr_features": list(VQR_FEATURES),
              "target": "fuel_consumption_kg_s", "units": {"fuel_consumption_kg_s": "kg/s"},
              "array_keys": ["features", "vqr_features", "target", "vqr_target",
                             "record_id", "vessel_id", "time_index"]}
    (stage / "feature_schema.json").write_text(json.dumps(schema), encoding="utf-8")
    audit = {"source_run_id": run.name, "dataset_version": version,
             "canonical_sha256": canonical_hash,
             "totals": {"output_rows": 45},
             "per_vessel": {v: {"output_rows": 15} for v in EXPECTED_CONFIGS}}
    audit_path = etl / "etl_audit.json"
    audit_path.write_text(json.dumps(audit), encoding="utf-8")
    files = ("train.npz", "validation.npz", "feature_schema.json",
             "vqr_preprocessor.pkl", "vqr_target_scaler.pkl")
    manifest = {"dataset_id": DATASET_ID, "dataset_version": version,
                "source_run_id": run.name, "canonical_sha256": canonical_hash,
                "etl_audit_sha256": sha256_file(audit_path),
                "split_strategy": "per_vessel_chronological_70_15_15",
                "per_vessel": details,
                "partition_counts": {"train": 30, "validation": 12, "test": 3},
                "artifact_sha256": {name: sha256_file(stage / name) for name in files}}
    (stage / "split_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return run, version, canonical_hash


class FuelCastVQRTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.run, self.version, self.checksum = synthetic_vqr_run(Path(self.temp.name))

    def split(self):
        return load_saved_vqr_validation(self.run, self.version, self.checksum)

    def test_loader_contract_and_hashes(self) -> None:
        with self.assertRaisesRegex(ValueError, "absolute"):
            load_saved_vqr_validation(Path("relative"), self.version, self.checksum)
        split = self.split()
        self.assertEqual(split.train.features.shape, (30, 6))
        self.assertEqual(split.validation.features.shape, (12, 6))
        self.assertEqual(list(split.train.features), list(VQR_FEATURES))
        altered = self.run / "04_transformation" / "validation.npz"
        altered.write_bytes(altered.read_bytes() + b"tampered")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self.split()

    def test_training_only_sampling_and_scalers(self) -> None:
        split = self.split()
        a, sample_a = sample_training(split, 12)
        b, sample_b = sample_training(split, 12)
        np.testing.assert_array_equal(a, b)
        self.assertEqual(sample_a, sample_b)
        self.assertEqual(sample_a["per_vessel_sampled"], {v: 4 for v in EXPECTED_CONFIGS})
        self.assertFalse(set(sample_a["record_ids"]) & set(split.validation.record_id))
        scaler = joblib.load(split.target_scaler_path)
        self.assertEqual(float(scaler.data_max_[0]), float(split.train.target.max()))
        self.assertGreater(float(split.validation.target.max()), float(scaler.data_max_[0]))
        restored = scaler.inverse_transform(split.validation.scaled_target.reshape(-1, 1)).reshape(-1)
        np.testing.assert_allclose(restored, split.validation.target)

    def test_no_test_artifact_access(self) -> None:
        original_open = Path.open
        original_stat = Path.stat
        def guarded_open(path, *args, **kwargs):
            if str(path).endswith("test.npz"):
                raise AssertionError("test artifact opened")
            return original_open(path, *args, **kwargs)
        def guarded_stat(path, *args, **kwargs):
            if str(path).endswith("test.npz"):
                raise AssertionError("test artifact statted")
            return original_stat(path, *args, **kwargs)
        with patch.object(Path, "open", guarded_open), patch.object(Path, "stat", guarded_stat):
            split = self.split()
            self.assertEqual(len(split.validation.target), 12)

    def test_coherent_schema_reorder_rejected(self) -> None:
        stage = self.run / "04_transformation"
        schema_path = stage / "feature_schema.json"
        schema = json.loads(schema_path.read_text())
        schema["vqr_features"] = list(reversed(schema["vqr_features"]))
        schema_path.write_text(json.dumps(schema), encoding="utf-8")
        manifest_path = stage / "split_manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["artifact_sha256"]["feature_schema.json"] = sha256_file(schema_path)
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "feature or split contract"):
            self.split()

    @unittest.skipUnless(QUANTUM_SMOKE, "set GREENFLEET_RUN_QUANTUM_SMOKE=1 for quantum smoke")
    def test_tiny_simulator_smoke(self) -> None:
        (_, _, _, _, VQR, _, COBYLA, QMLEstimator) = quantum_dependencies()
        from qiskit_machine_learning.optimizers import SPSA
        from qiskit_machine_learning.utils import algorithm_globals
        algorithm_globals.random_seed = 42
        x = np.array([[0.1, 0.2, 0.3, 0.4, 0.5, 0.6],
                      [0.2, 0.3, 0.4, 0.5, 0.6, 0.7],
                      [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]])
        y = np.array([-0.2, 0.0, 0.2])
        for reps in (1, 2):
            feature_map, ansatz, observable = build_vqr_circuits(reps)
            self.assertEqual((feature_map.num_qubits, feature_map.num_parameters), (6, 6))
            self.assertEqual((ansatz.num_qubits, ansatz.num_parameters), (6, 6 * (reps + 1)))
            self.assertEqual(ansatz.count_ops()["cx"], 5 * reps)
            for optimizer_name in ("COBYLA", "SPSA"):
                with self.subTest(reps=reps, optimizer=optimizer_name):
                    optimizer = (COBYLA(maxiter=ansatz.num_parameters + 2)
                                 if optimizer_name == "COBYLA"
                                 else SPSA(maxiter=1, learning_rate=0.05, perturbation=0.1))
                    model = VQR(
                        feature_map=feature_map, ansatz=ansatz, observable=observable,
                        estimator=QMLEstimator(default_precision=0.0),
                        optimizer=optimizer, loss="squared_error",
                        initial_point=np.zeros(ansatz.num_parameters),
                    )
                    model.fit(x, y)
                    prediction = np.asarray(model.predict(x))
                    self.assertEqual(prediction.shape, (3, 1))
                    self.assertTrue(np.isfinite(prediction).all())

    @unittest.skipUnless(QUANTUM_SMOKE, "set GREENFLEET_RUN_QUANTUM_SMOKE=1 for quantum smoke")
    def test_synthetic_quick_cli(self) -> None:
        feature_map, ansatz, observable = build_vqr_circuits()
        self.assertEqual((feature_map.num_qubits, feature_map.num_parameters), (6, 6))
        self.assertEqual((ansatz.num_qubits, ansatz.num_parameters), (6, 12))
        self.assertEqual(ansatz.count_ops()["cx"], 5)
        self.assertEqual(observable.num_qubits, 6)
        command = [sys.executable, "-m", "greenfleet.ml_pipeline.quantum.fuelcast_vqr",
                   "train", "--run-dir", str(self.run), "--mode", "quick",
                   "--expected-version", self.version,
                   "--expected-canonical-sha256", self.checksum]
        subprocess.run(command, check=True, capture_output=True, text=True)
        candidate = self.run / "06_quantum" / "vqr" / "quick" / "candidate"
        manifest = verify_candidate(self.run, candidate)
        self.assertEqual(manifest["model_family"], "quantum")
        self.assertEqual(manifest["backend"], "simulator")
        self.assertFalse(manifest["real_quantum_hardware"])
        self.assertEqual(manifest["validation_rows"], 12)
        self.assertLessEqual(manifest["optimizer_evaluations"], VQR_MODES["quick"]["maxiter"])
        self.assertNotIn("test_metrics", manifest)
        with np.load(candidate / "validation_predictions.npz", allow_pickle=False) as saved:
            prediction = saved["prediction"]
            self.assertEqual(saved["record_id"].tolist(), self.split().validation.record_id.tolist())
        split = self.split()
        self.assertAlmostEqual(manifest["validation_metrics"]["mae"],
                               mean_absolute_error(split.validation.target, prediction))
        self.assertAlmostEqual(manifest["validation_metrics"]["rmse"],
                               np.sqrt(mean_squared_error(split.validation.target, prediction)))
        self.assertAlmostEqual(manifest["validation_metrics"]["r2"],
                               r2_score(split.validation.target, prediction))
        for vessel in EXPECTED_CONFIGS:
            mask = split.validation.vessel_id == vessel
            measured = manifest["validation_per_vessel"][vessel]
            self.assertEqual(measured["rows"], int(mask.sum()))
            self.assertAlmostEqual(measured["mae"],
                                   mean_absolute_error(split.validation.target[mask], prediction[mask]))
        loaded = load_vqr_candidate(candidate, self.split())
        raw = pd.DataFrame([[3.0, 1.2, 90.0, 0.5, 3.0, 0.2]], columns=VQR_FEATURES)
        one = loaded.predict(raw)
        self.assertEqual(one.shape, (1,))
        self.assertTrue(np.isfinite(one).all())
        with self.assertRaisesRegex(ValueError, "canonical columns"):
            loaded.predict(raw[list(reversed(VQR_FEATURES))])
        fresh = subprocess.run(
            [sys.executable, "-m", "greenfleet.ml_pipeline.quantum.fuelcast_vqr",
             "verify", "--run-dir", str(self.run), "--candidate-dir", str(candidate)],
            check=True, capture_output=True, text=True,
        )
        self.assertIn("Verified", fresh.stdout)

    @unittest.skipUnless(QUANTUM_SMOKE, "set GREENFLEET_RUN_QUANTUM_SMOKE=1 for quantum smoke")
    def test_fresh_process_reconstruction(self) -> None:
        artifact = train_vqr(FuelCastVQRConfig(self.run, "quick", self.version, self.checksum))
        loaded = load_vqr_candidate(artifact.candidate_dir, self.split())
        one = loaded.predict_angles(self.split().validation.features.iloc[[0]])
        self.assertEqual(one.shape, (1,))
        subprocess.run(
            [sys.executable, "-m", "greenfleet.ml_pipeline.quantum.fuelcast_vqr",
             "verify", "--run-dir", str(self.run), "--candidate-dir", str(artifact.candidate_dir)],
            check=True, capture_output=True, text=True,
        )

    @unittest.skipUnless(QUANTUM_SMOKE, "set GREENFLEET_RUN_QUANTUM_SMOKE=1 for quantum smoke")
    def test_artifact_tamper_rejected_before_external_access(self) -> None:
        artifact = train_vqr(FuelCastVQRConfig(self.run, "quick", self.version, self.checksum))
        candidate = artifact.candidate_dir
        for name in ("weights.npz", "circuit_config.json"):
            path = candidate / name
            original = path.read_bytes()
            path.write_bytes(original + b"tampered")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                load_vqr_candidate(candidate)
            path.write_bytes(original)
        manifest_path = candidate / "candidate_manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["artifact_sha256"]["test.npz"] = "0" * 64
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with patch("greenfleet.ml_pipeline.quantum.fuelcast_vqr_model.sha256_file",
                   side_effect=AssertionError("must reject before hashing")):
            with self.assertRaisesRegex(ValueError, "artifact set mismatch"):
                load_vqr_candidate(candidate)

    def test_optional_dependency_message(self) -> None:
        import builtins
        original_import = builtins.__import__
        def unavailable(name, *args, **kwargs):
            if name == "qiskit" or name.startswith("qiskit_machine_learning"):
                raise ImportError("simulated missing optional dependency")
            return original_import(name, *args, **kwargs)
        with patch("builtins.__import__", side_effect=unavailable):
            with self.assertRaisesRegex(RuntimeError, "requirements-vqr.txt"):
                quantum_dependencies()

    @unittest.skipUnless(QUANTUM_SMOKE, "set GREENFLEET_RUN_QUANTUM_SMOKE=1 for quantum smoke")
    def test_timeout_leaves_no_published_candidate(self) -> None:
        config = FuelCastVQRConfig(self.run, "quick", self.version, self.checksum)
        with patch.dict(VQR_MODES["quick"], {"fit_wall_seconds": -1}):
            with self.assertRaises(TimeoutError):
                train_vqr(config)
        self.assertFalse((self.run / "06_quantum" / "vqr" / "quick").exists())
        staging = list((self.run / "06_quantum" / "vqr").glob(".quick-staging-*"))
        self.assertEqual(len(staging), 1)
        self.assertTrue((staging[0] / "candidate" / "optimizer_history.json").exists())

    @unittest.skipUnless(QUANTUM_SMOKE, "set GREENFLEET_RUN_QUANTUM_SMOKE=1 for quantum smoke")
    def test_full_trainer_guard_and_checkpoint_restart(self) -> None:
        original_open = Path.open
        original_stat = Path.stat
        def guard_open(path, *args, **kwargs):
            if str(path).endswith("test.npz"):
                raise AssertionError("test artifact opened")
            return original_open(path, *args, **kwargs)
        def guard_stat(path, *args, **kwargs):
            if str(path).endswith("test.npz"):
                raise AssertionError("test artifact statted")
            return original_stat(path, *args, **kwargs)
        with patch.object(Path, "open", guard_open), patch.object(Path, "stat", guard_stat):
            with patch.dict(VQR_MODES["quick"], {"fit_wall_seconds": -1}):
                with self.assertRaises(TimeoutError):
                    train_vqr(FuelCastVQRConfig(self.run, "quick", self.version, self.checksum))
            staging = next((self.run / "06_quantum" / "vqr").glob(".quick-staging-*"))
            checkpoint = staging / "candidate"
            previous = json.loads((checkpoint / "attempt_manifest.json").read_text())
            resumed = train_vqr(FuelCastVQRConfig(
                self.run, "quick", self.version, self.checksum,
                resume_checkpoint=checkpoint,
            ))
        manifest = json.loads(resumed.manifest_path.read_text())
        self.assertEqual(manifest["resumed_from_attempt_id"], previous["attempt_id"])
        self.assertEqual(manifest["validation_rows"], 12)


if __name__ == "__main__":
    unittest.main()
