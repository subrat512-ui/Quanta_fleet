"""Offline Phase 5 contract and candidate reload tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from greenfleet.config.fuelcast_classical_config import FuelCastClassicalConfig
from greenfleet.constants.fuelcast import CANONICAL_FEATURES, CANONICAL_TARGET, DATASET_ID, EXPECTED_CONFIGS
from greenfleet.constants.fuelcast_classical import CANDIDATES, CLASSICAL_FEATURES, SEARCHES
from greenfleet.ml_pipeline.training.fuelcast_classical import (
    _sample_training, train_classical, verify_candidate,
)
from greenfleet.ml_pipeline.training.fuelcast_classical_model import load_classical_candidate
from greenfleet.ml_pipeline.training.fuelcast_data import load_saved_validation, sha256_file


def synthetic_run(root: Path, rows_per_vessel: int = 24) -> tuple[Path, str, str]:
    run = root / "synthetic-fuelcast-run"
    etl = run / "02_etl"
    stage = run / "04_transformation"
    etl.mkdir(parents=True)
    stage.mkdir()
    version = "a" * 40
    canonical = etl / "fuelcast_clean.csv"
    canonical.write_text("invented synthetic canonical fixture\n", encoding="utf-8")
    checksum = sha256_file(canonical)
    audit = {"source_run_id": run.name, "dataset_version": version,
             "canonical_sha256": checksum,
             "totals": {"output_rows": 24 * len(EXPECTED_CONFIGS)},
             "per_vessel": {vessel: {"output_rows": 24} for vessel in EXPECTED_CONFIGS}}
    audit_path = etl / "etl_audit.json"
    audit_path.write_text(json.dumps(audit), encoding="utf-8")
    schema = {
        "dataset_id": DATASET_ID, "dataset_version": version,
        "raw_features": list(CANONICAL_FEATURES),
        "classical_features": list(CLASSICAL_FEATURES),
        "target": CANONICAL_TARGET, "units": {CANONICAL_TARGET: "kg/s"},
        "array_keys": ["features", "vqr_features", "target", "vqr_target",
                       "record_id", "vessel_id", "time_index"],
    }
    schema_path = stage / "feature_schema.json"
    schema_path.write_text(json.dumps(schema), encoding="utf-8")
    preprocessor_path = stage / "preprocessor.pkl"
    preprocessor_path.write_bytes(b"synthetic placeholder; never loaded")
    details = {vessel: {} for vessel in EXPECTED_CONFIGS}
    counts = {}
    for name, begin, end in (("train", 0, 16), ("validation", 16, 20)):
        rows = []
        ids = []
        vessels = []
        times = []
        target = []
        for vessel_number, vessel in enumerate(EXPECTED_CONFIGS):
            vessel_ids = []
            for index in range(begin, end):
                speed = float(index) / 10 + vessel_number
                rows.append([speed, float(index % 5), 0.0, 1.0,
                             float(index % 3), float(index % 4), vessel_number / 2])
                target.append(1 + speed / 4 + (index % 3) / 20)
                identity = f"{vessel}-{index}"
                ids.append(identity)
                vessel_ids.append(identity)
                vessels.append(vessel)
                times.append(index)
            details[vessel][name] = {
                "count": end - begin, "first_time_index": begin,
                "last_time_index": end - 1, "record_ids": vessel_ids,
            }
        counts[name] = len(ids)
        np.savez_compressed(stage / f"{name}.npz", features=np.asarray(rows),
                            vqr_features=np.zeros((len(ids), 6)),
                            target=np.asarray(target), vqr_target=np.zeros(len(ids)),
                            record_id=np.asarray(ids), vessel_id=np.asarray(vessels),
                            time_index=np.asarray(times, dtype=np.int64))
    for vessel in EXPECTED_CONFIGS:
        details[vessel]["test"] = {
            "count": 4, "first_time_index": 20,
            "last_time_index": 23,
            "record_ids": [f"{vessel}-{index}" for index in range(20, 24)],
        }
    counts["test"] = 4 * len(EXPECTED_CONFIGS)
    hashes = {name: sha256_file(stage / name) for name in (
        "train.npz", "validation.npz", "feature_schema.json", "preprocessor.pkl")}
    manifest = {
        "dataset_id": DATASET_ID, "dataset_version": version,
        "source_run_id": run.name, "canonical_sha256": checksum,
        "etl_audit_sha256": sha256_file(audit_path),
        "split_strategy": "per_vessel_chronological_70_15_15",
        "per_vessel": details, "partition_counts": counts,
        "artifact_sha256": hashes,
    }
    (stage / "split_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return run, version, checksum


class FuelCastClassicalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.run, self.version, self.checksum = synthetic_run(Path(self.temp.name))

    def split(self):
        return load_saved_validation(self.run, self.version, self.checksum)

    def test_explicit_run_schema_and_hashes(self) -> None:
        with self.assertRaisesRegex(ValueError, "absolute"):
            load_saved_validation(Path("relative"), self.version, self.checksum)
        with self.assertRaisesRegex(ValueError, "provenance"):
            load_saved_validation(self.run, self.version, "wrong")
        split = self.split()
        self.assertEqual(split.train.features.shape, (48, 7))
        self.assertEqual(split.validation.features.shape, (12, 7))
        self.assertEqual(list(split.train.features), list(CLASSICAL_FEATURES))
        path = self.run / "04_transformation" / "validation.npz"
        path.write_bytes(path.read_bytes() + b"tampered")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self.split()

    def test_partition_counts_match_etl_audit(self) -> None:
        audit_path = self.run / "02_etl" / "etl_audit.json"
        audit = json.loads(audit_path.read_text())
        audit["totals"]["output_rows"] += 1
        audit_path.write_text(json.dumps(audit), encoding="utf-8")
        manifest_path = self.run / "04_transformation" / "split_manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["etl_audit_sha256"] = sha256_file(audit_path)
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "partition counts"):
            self.split()

    def test_no_test_artifact_access(self) -> None:
        original_open = Path.open
        def guarded_open(path, *args, **kwargs):
            if str(path).endswith("test.npz"):
                raise AssertionError("test artifact accessed")
            return original_open(path, *args, **kwargs)
        with patch.object(Path, "open", guarded_open):
            split = self.split()
            self.assertEqual(len(_sample_training(split, "quick")), 48)

    def test_search_contract(self) -> None:
        self.assertEqual(tuple(SEARCHES["quick"]), CANDIDATES)
        self.assertEqual([SEARCHES["quick"][name][2] for name in CANDIDATES], [3, 2, 2, 2])
        self.assertEqual([SEARCHES["normal"][name][2] for name in CANDIDATES], [5, 6, 6, 8])

    def test_atomic_failure_and_full_path_test_guard(self) -> None:
        import greenfleet.ml_pipeline.training.fuelcast_classical as module
        original_open = Path.open
        original_save = module._save_candidate
        calls = 0
        def guarded_open(path, *args, **kwargs):
            if str(path).endswith("test.npz"):
                raise AssertionError("test artifact accessed")
            return original_open(path, *args, **kwargs)
        def fail_second(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("injected search failure")
            return original_save(*args, **kwargs)
        with patch.object(Path, "open", guarded_open), patch.object(module, "_save_candidate", side_effect=fail_second):
            with self.assertRaisesRegex(RuntimeError, "injected search failure"):
                train_classical(FuelCastClassicalConfig(self.run, "quick", self.version, self.checksum))
        self.assertEqual(calls, 2)
        self.assertFalse((self.run / "05_classical" / "quick").exists())
        self.assertFalse(list((self.run / "05_classical").glob(".quick-staging-*")))

    def test_synthetic_quick_cli(self) -> None:
        command = [sys.executable, "-m", "greenfleet.ml_pipeline.training.fuelcast_classical",
                   "train", "--run-dir", str(self.run), "--mode", "quick",
                   "--expected-version", self.version,
                   "--expected-canonical-sha256", self.checksum]
        subprocess.run(command, check=True, capture_output=True, text=True)
        published = self.run / "05_classical" / "quick"
        board = json.loads((published / "classical_leaderboard.json").read_text())
        self.assertEqual(board["selection_scope"], "classical_validation_only")
        self.assertEqual({item["candidate"] for item in board["candidates"]}, set(CANDIDATES))
        self.assertEqual([item["rank"] for item in board["candidates"]], [1, 2, 3, 4])
        self.assertEqual([item["validation_metrics"]["mae"] for item in board["candidates"]],
                         sorted(item["validation_metrics"]["mae"] for item in board["candidates"]))
        self.assertNotIn("test", json.dumps(board).lower())
        for name in CANDIDATES:
            candidate_dir = published / name
            manifest = verify_candidate(self.run, candidate_dir)
            self.assertEqual(manifest["validation_rows"], 12)
            self.assertEqual(manifest["training_rows_sampled"], 48)
            self.assertEqual(manifest["backend"], "cpu")
            self.assertEqual(manifest["hardware"], "classical")
            self.assertEqual(len(manifest["training_sample_record_ids"]), 48)
            self.assertEqual(len(json.loads((candidate_dir / "search_results.json").read_text())["trials"]),
                             SEARCHES["quick"][name][2])
            self.assertNotIn("test_metrics", manifest)
            with np.load(candidate_dir / "validation_predictions.npz", allow_pickle=False) as saved:
                prediction = saved["prediction"]
                self.assertEqual(saved["record_id"].tolist(), self.split().validation.record_id.tolist())
            truth = self.split().validation.target
            self.assertAlmostEqual(manifest["validation_metrics"]["mae"],
                                   mean_absolute_error(truth, prediction))
            self.assertAlmostEqual(manifest["validation_metrics"]["rmse"],
                                   np.sqrt(mean_squared_error(truth, prediction)))
            self.assertAlmostEqual(manifest["validation_metrics"]["r2"],
                                   r2_score(truth, prediction))
            loaded = load_classical_candidate(candidate_dir, self.split())
            frame = self.split().validation.features
            self.assertEqual(loaded.predict(frame).shape, (12,))
            with self.assertRaisesRegex(ValueError, "seven named columns"):
                loaded.predict(frame[list(reversed(CLASSICAL_FEATURES))])
            with self.assertRaisesRegex(ValueError, "seven named columns"):
                loaded.predict(frame.to_numpy())
        with self.assertRaises(FileExistsError):
            train_classical(FuelCastClassicalConfig(self.run, "quick", self.version, self.checksum))

    def test_deterministic_trial_order_and_scores(self) -> None:
        first = train_classical(FuelCastClassicalConfig(self.run, "quick", self.version, self.checksum))
        other_temp = tempfile.TemporaryDirectory()
        self.addCleanup(other_temp.cleanup)
        other_run, version, checksum = synthetic_run(Path(other_temp.name))
        second = train_classical(FuelCastClassicalConfig(other_run, "quick", version, checksum))
        for candidate in CANDIDATES:
            trial_a = json.loads((first / candidate / "search_results.json").read_text())["trials"]
            trial_b = json.loads((second / candidate / "search_results.json").read_text())["trials"]
            self.assertEqual([trial["parameters"] for trial in trial_a],
                             [trial["parameters"] for trial in trial_b])
            np.testing.assert_allclose([trial["validation_mae"] for trial in trial_a],
                                       [trial["validation_mae"] for trial in trial_b], rtol=0, atol=1e-12)

    def test_reload_fresh_process(self) -> None:
        published = train_classical(FuelCastClassicalConfig(
            self.run, "quick", self.version, self.checksum,
        ))
        result = subprocess.run([
            sys.executable, "-m", "greenfleet.ml_pipeline.training.fuelcast_classical",
            "verify", "--run-dir", str(self.run),
            "--candidate-dir", str(published / "xgboost"),
        ], check=True, capture_output=True, text=True)
        self.assertIn("Verified FuelCast candidate: xgboost", result.stdout)

    def test_missing_xgboost_is_actionable(self) -> None:
        import greenfleet.ml_pipeline.training.fuelcast_classical as module
        with patch.object(module, "_xgboost", side_effect=RuntimeError("install with python -m pip install -r requirements.txt")):
            with self.assertRaisesRegex(RuntimeError, "pip install"):
                train_classical(FuelCastClassicalConfig(self.run, "quick", self.version, self.checksum))
        self.assertFalse((self.run / "05_classical" / "quick").exists())


if __name__ == "__main__":
    unittest.main()
