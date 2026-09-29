"""Offline Phase 8 metric, freeze, identity, and package contracts."""

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
import joblib
import sklearn
from sklearn.linear_model import Ridge

from greenfleet.constants.fuelcast import EXPECTED_CONFIGS
from greenfleet.ml_pipeline.evaluation import fuelcast as phase8
from greenfleet.ml_pipeline.training.fuelcast_data import sha256_file
from greenfleet.ml_pipeline.training.fuelcast_data import load_saved_validation
from greenfleet.ml_pipeline.transformation.fuelcast import run_fuelcast_transformation
from test_fuelcast_transformation import make_run


class FuelCastModelSelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.run = make_run(Path(self.temp.name))
        run_fuelcast_transformation(self.run)
        stage = self.run / "04_transformation"
        split = json.loads((stage / "split_manifest.json").read_text())
        self.selection = {
            "split_manifest_sha256": sha256_file(stage / "split_manifest.json"),
            "feature_schema_sha256": sha256_file(stage / "feature_schema.json"),
            "dataset_version": split["dataset_version"],
            "canonical_sha256": split["canonical_sha256"],
        }

    def test_known_metrics_and_vessel_grouping(self):
        y = np.array([0., 1., 2., 3., 4., 5.])
        p = np.array([0., 2., 1., 3., 5., 4.])
        result = phase8.metrics(y, p)
        self.assertAlmostEqual(result["mae"], 4 / 6)
        self.assertAlmostEqual(result["rmse"], np.sqrt(4 / 6))
        self.assertAlmostEqual(result["r2"], 1 - 4 / 17.5)
        groups = phase8._grouped(y, p, np.repeat(EXPECTED_CONFIGS, 2))
        self.assertEqual([groups[v]["rows"] for v in EXPECTED_CONFIGS], [2, 2, 2])
        with self.assertRaisesRegex(ValueError, "differ"):
            phase8.metrics(y, p[:-1])
        with self.assertRaisesRegex(ValueError, "non-finite"):
            phase8.metrics(y, np.full(6, np.nan))
        with self.assertRaisesRegex(ValueError, "coverage"):
            phase8._grouped(y, p, np.repeat(EXPECTED_CONFIGS[0], 6))

    def test_validation_ranking_and_exact_tie(self):
        names = ("vqr", "xgboost", "ridge", "random_forest", "gradient_boosting")
        rows = [{"candidate": name, "validation_metrics": {"mae": 0.2},
                 "test_metrics": {"mae": 0.0 if name == "xgboost" else 100.0}}
                for name in names]
        ordered = phase8._rank_candidates(rows)
        self.assertEqual([row["candidate"] for row in ordered], sorted(names))
        rows[0]["validation_metrics"]["mae"] = 0.1
        self.assertEqual(phase8._rank_candidates(rows)[0]["candidate"], "vqr")
        self.assertNotEqual(phase8._rank_candidates(rows)[0]["candidate"], "xgboost")
        with self.assertRaisesRegex(ValueError, "incomplete"):
            phase8._rank_candidates(rows[:-1])

    def test_test_partition_identity_and_hash(self):
        arrays = phase8.load_saved_test(self.run, self.selection)
        self.assertEqual(len(arrays["record_id"]), 9)
        self.assertEqual(len(set(arrays["record_id"])), 9)
        test_path = self.run / "04_transformation" / "test.npz"
        test_path.write_bytes(test_path.read_bytes() + b"tamper")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            phase8.load_saved_test(self.run, self.selection)

    def test_test_partition_rejects_duplicate_even_if_rehashed(self):
        stage = self.run / "04_transformation"
        test_path = stage / "test.npz"
        with np.load(test_path, allow_pickle=False) as stored:
            arrays = {key: stored[key] for key in stored.files}
        arrays["record_id"][1] = arrays["record_id"][0]
        np.savez_compressed(test_path, **arrays)
        split_path = stage / "split_manifest.json"
        split = json.loads(split_path.read_text())
        split["artifact_sha256"]["test.npz"] = sha256_file(test_path)
        split_path.write_text(json.dumps(split))
        self.selection["split_manifest_sha256"] = sha256_file(split_path)
        with self.assertRaisesRegex(ValueError, "identities"):
            phase8.load_saved_test(self.run, self.selection)

    def test_test_partition_rejects_nonfinite_even_if_rehashed(self):
        stage = self.run / "04_transformation"
        path = stage / "test.npz"
        with np.load(path, allow_pickle=False) as stored:
            arrays = {key: stored[key] for key in stored.files}
        arrays["features"][0, 0] = np.nan
        np.savez_compressed(path, **arrays)
        split_path = stage / "split_manifest.json"
        split = json.loads(split_path.read_text())
        split["artifact_sha256"]["test.npz"] = sha256_file(path)
        split_path.write_text(json.dumps(split))
        self.selection["split_manifest_sha256"] = sha256_file(split_path)
        with self.assertRaisesRegex(ValueError, "invalid shape or values"):
            phase8.load_saved_test(self.run, self.selection)

    def test_selection_does_not_open_test(self):
        version = self.selection["dataset_version"]
        canonical = self.selection["canonical_sha256"]
        original = Path.open
        def guarded(path, *args, **kwargs):
            if path.name == "test.npz":
                raise AssertionError("test was opened during selection")
            return original(path, *args, **kwargs)
        with patch.object(Path, "open", guarded):
            with self.assertRaisesRegex(ValueError, "regular FuelCast file"):
                phase8.select_fuelcast_champion(self.run, version, canonical)

    def test_validation_prediction_alignment(self):
        from greenfleet.ml_pipeline.training.fuelcast_data import load_saved_validation
        split = load_saved_validation(self.run, self.selection["dataset_version"],
                                      self.selection["canonical_sha256"])
        path = self.run / "prediction.npz"
        part = split.validation
        np.savez_compressed(path, record_id=part.record_id[::-1], vessel_id=part.vessel_id,
                            time_index=part.time_index, prediction=part.target)
        with self.assertRaisesRegex(ValueError, "identity aligned"):
            phase8._prediction_file(path, part)

    def test_frozen_selection_precedes_test_access(self):
        with self.assertRaisesRegex(ValueError, "regular FuelCast file"):
            phase8.evaluate_frozen_champion(self.run)
        self.assertFalse((self.run / "07_evaluation").exists())

    def _ridge_candidate(self):
        split = load_saved_validation(self.run, self.selection["dataset_version"],
                                      self.selection["canonical_sha256"])
        path = self.run / "05_classical" / "normal" / "ridge"
        path.mkdir(parents=True)
        model = Ridge().fit(split.train.features, split.train.target)
        joblib.dump(model, path / "model.joblib")
        (path / "search_results.json").write_text("{}\n")
        predicted = model.predict(split.validation.features)
        np.savez_compressed(path / "validation_predictions.npz",
                            record_id=split.validation.record_id,
                            vessel_id=split.validation.vessel_id,
                            time_index=split.validation.time_index,
                            prediction=predicted)
        manifest = {
            "candidate": "ridge", "model_family": "classical", "backend": "cpu",
            "hardware": "classical", "mode": "normal", "model_file": "model.joblib",
            "feature_order": list(split.train.features.columns),
            "target": "fuel_consumption_kg_s", "target_unit": "kg/s",
            "dataset_id": "krohnedigital/FuelCast", "run_id": self.run.name,
            "dataset_version": split.dataset_version, "canonical_sha256": split.canonical_sha256,
            "feature_schema_sha256": split.schema_sha256,
            "split_manifest_sha256": split.split_manifest_sha256,
            "phase4_artifact_sha256": split.source_hashes,
            "training_rows_full": len(split.train.target),
            "training_rows_sampled": len(split.train.target),
            "validation_rows": len(predicted), "partition_counts": split.partition_counts,
            "validation_metrics": phase8.metrics(split.validation.target, predicted),
            "validation_per_vessel": phase8._grouped(split.validation.target, predicted,
                                                       split.validation.vessel_id),
            "fit_seconds": 1.0, "prediction_seconds": 1.0,
            "dependency_versions": {"scikit_learn": sklearn.__version__,
                                    "numpy": np.__version__, "pandas": pd.__version__,
                                    "joblib": joblib.__version__},
            "artifact_sha256": {name: sha256_file(path / name) for name in
                                ("model.joblib", "search_results.json",
                                 "validation_predictions.npz")},
        }
        (path / "candidate_manifest.json").write_text(json.dumps(manifest))
        return path, split

    def test_successful_selection_package_reload_and_single_test(self):
        ridge_path, split = self._ridge_candidate()
        ridge_result = phase8._candidate_result("ridge", ridge_path, split, None)
        original = phase8._candidate_result
        def candidates(name, path, classical, quantum):
            if name == "ridge":
                return original(name, path, classical, quantum)
            value = dict(ridge_result)
            value.update(candidate=name, model_family="quantum" if name == "vqr" else "classical",
                         backend="simulator" if name == "vqr" else "cpu")
            value["validation_metrics"] = {**ridge_result["validation_metrics"],
                                           "mae": ridge_result["validation_metrics"]["mae"] + 1.0}
            return value
        with patch.object(phase8, "_candidate_result", side_effect=candidates), \
             patch.object(Ridge, "fit", side_effect=AssertionError("unexpected refit")):
            original_np_load = np.load
            def guarded_np_load(path, *args, **kwargs):
                if str(path).endswith("test.npz"):
                    raise AssertionError("test opened during selection")
                return original_np_load(path, *args, **kwargs)
            with patch.object(np, "load", side_effect=guarded_np_load):
                frozen = phase8.select_fuelcast_champion(
                    self.run, self.selection["dataset_version"], self.selection["canonical_sha256"])
            self.assertEqual(frozen["champion_model"], "ridge")
            self.assertFalse(frozen["refit"])
            loaded = phase8.load_final_model(Path(self.temp.name) / "final_model")
            sample = pd.DataFrame([[2., 1., 90., 1., 5., .3]], columns=loaded.manifest["raw_features"])
            self.assertTrue(np.isfinite(loaded.predict(sample)).all())
            completed = phase8.evaluate_frozen_champion(self.run)
        self.assertEqual(completed["champion_model"], "ridge")
        self.assertEqual(completed["test_rows"], 9)
        with np.load(self.run / "07_evaluation" / "test_predictions.npz", allow_pickle=False) as saved:
            self.assertEqual(len(set(saved["record_id"])), 9)
            self.assertEqual(set(saved.files), {"record_id", "vessel_id", "time_index",
                                                "target", "prediction"})
        with self.assertRaises(FileExistsError):
            phase8.evaluate_frozen_champion(self.run)
        final = Path(self.temp.name) / "final_model"
        self.assertEqual(phase8.load_final_model(final).manifest["test_metrics"],
                         completed["test_metrics"])
        env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
        command = [sys.executable, "-m", "greenfleet.ml_pipeline.evaluation", "verify",
                   "--model-dir", str(final)]
        result = subprocess.run(command, env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Verified ridge", result.stdout)
        (final / "leaderboard.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            phase8.load_final_model(final)

    def test_vqr_inverse_target_scaling(self):
        from sklearn.preprocessing import MinMaxScaler
        from greenfleet.ml_pipeline.quantum.fuelcast_vqr_model import LoadedVQRCandidate
        scaler = MinMaxScaler(feature_range=(-1, 1)).fit(np.array([[2.], [6.]]))
        class ZeroQNN:
            def forward(self, rows, weights):
                return np.zeros((len(rows), 1))
        model = LoadedVQRCandidate(ZeroQNN(), np.zeros(12), None, scaler, {})
        features = pd.DataFrame(np.zeros((2, 6)), columns=[
            "speed_over_ground", "wind_speed", "wind_direction",
            "wave_height", "wave_period", "current_speed"])
        np.testing.assert_allclose(model.predict_angles(features), [4., 4.])

    def test_vqr_family_adapter_can_win_and_score_saved_test(self):
        from greenfleet.ml_pipeline.quantum.fuelcast_vqr_data import load_saved_vqr_validation
        split = load_saved_vqr_validation(self.run, self.selection["dataset_version"],
                                          self.selection["canonical_sha256"])
        candidate = self.run / "06_quantum" / "vqr" / "normal" / "candidate"
        candidate.mkdir(parents=True)
        predicted = np.full(len(split.validation.target), float(np.mean(split.train.target)))
        np.savez_compressed(candidate / "validation_predictions.npz",
                            record_id=split.validation.record_id,
                            vessel_id=split.validation.vessel_id,
                            time_index=split.validation.time_index,
                            prediction=predicted)
        reported = {"validation_rows": len(predicted), "benchmark_eligible": True,
                    "validation_metrics": phase8.metrics(split.validation.target, predicted)}
        (candidate / "validation_metrics.json").write_text(json.dumps(reported))
        (candidate / "weights.npz").write_bytes(b"synthetic weights")
        manifest = {"candidate": "vqr", "model_family": "quantum", "backend": "simulator",
                    "hardware": "simulator", "mode": "normal", "benchmark_eligible": True,
                    "dataset_id": "krohnedigital/FuelCast", "dataset_version": split.dataset_version,
                    "canonical_sha256": split.canonical_sha256, "run_id": self.run.name,
                    "feature_schema_sha256": split.schema_sha256,
                    "split_manifest_sha256": split.split_manifest_sha256,
                    "phase4_artifact_sha256": split.source_hashes,
                    "training_rows_full": len(split.train.target),
                    "training_rows_sampled": len(split.train.target),
                    "validation_rows": len(predicted), "partition_counts": split.partition_counts,
                    "validation_metrics": reported["validation_metrics"],
                    "validation_per_vessel": phase8._grouped(split.validation.target, predicted,
                                                               split.validation.vessel_id),
                    "fit_seconds": 1., "prediction_seconds": 1.,
                    "dependency_versions": {"synthetic": "1"},
                    "artifact_sha256": {name: sha256_file(candidate / name) for name in
                                        ("validation_predictions.npz", "validation_metrics.json",
                                         "weights.npz")}}
        (candidate / "candidate_manifest.json").write_text(json.dumps(manifest))
        class FakeVQR:
            def predict_angles(self, features):
                return np.full(len(features), predicted[0])
            def predict(self, features):
                return np.full(len(features), predicted[0])
        actual_candidate = phase8._candidate_result
        def result(name, path, classical, quantum):
            if name == "vqr":
                return actual_candidate(name, path, classical, quantum)
            row = dict(actual_candidate("vqr", candidate, classical, quantum))
            row["candidate"] = name
            row["validation_metrics"] = {**row["validation_metrics"],
                                         "mae": row["validation_metrics"]["mae"] + 1.}
            return row
        with patch.object(phase8, "load_vqr_candidate", return_value=FakeVQR()), \
             patch.object(phase8, "_candidate_result", side_effect=result):
            frozen = phase8.select_fuelcast_champion(
                self.run, self.selection["dataset_version"], self.selection["canonical_sha256"])
            self.assertEqual(frozen["champion_model"], "vqr")
            loaded = phase8.load_final_model(Path(self.temp.name) / "final_model")
            self.assertEqual(loaded.manifest["model_family"], "quantum")
            report = phase8.evaluate_frozen_champion(self.run)
            self.assertEqual(report["test_rows"], 9)
            self.assertEqual(report["champion_model"], "vqr")


if __name__ == "__main__":
    unittest.main()
