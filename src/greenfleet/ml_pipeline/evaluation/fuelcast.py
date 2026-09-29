"""Validation-only selection, immutable package, and one final FuelCast test."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from greenfleet.constants.fuelcast import CANONICAL_FEATURES, CANONICAL_TARGET, DATASET_ID, EXPECTED_CONFIGS
from greenfleet.constants.fuelcast_classical import CANDIDATES, CLASSICAL_FEATURES
from greenfleet.ml_pipeline.quantum.fuelcast_vqr_data import load_saved_vqr_validation
from greenfleet.ml_pipeline.quantum.fuelcast_vqr_model import load_vqr_candidate
from greenfleet.ml_pipeline.training.fuelcast_classical_model import load_classical_candidate
from greenfleet.ml_pipeline.training.fuelcast_data import load_saved_validation, sha256_file


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _regular(path: Path) -> Path:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Expected regular FuelCast file: {path}")
    return path


def _switch_link(public: Path, target: Path) -> None:
    """Replace one public symlink only after its complete backing exists."""
    temporary = public.with_name(f".{public.name}-next-{os.getpid()}")
    if os.path.lexists(temporary):
        raise FileExistsError(temporary)
    try:
        temporary.symlink_to(target.name, target_is_directory=True)
        os.replace(temporary, public)
    finally:
        temporary.unlink(missing_ok=True)


def _recover_transaction(run_dir: Path) -> None:
    marker = run_dir / ".phase8-evaluation-transaction.json"
    if not marker.exists():
        return
    transaction = _json(marker)
    final = run_dir.parent / "final_model"
    evaluation = run_dir / "07_evaluation"
    if not final.is_symlink() or not evaluation.is_symlink():
        raise ValueError("FuelCast interrupted evaluation needs manual recovery")
    old_final = run_dir.parent / transaction["old_final"]
    old_evaluation = run_dir / transaction["old_evaluation"]
    if not old_final.is_dir() or not old_evaluation.is_dir():
        raise ValueError("FuelCast interrupted evaluation backing is missing")
    if (evaluation / "evaluation_manifest.json").exists():
        # Both public links already show a complete report; keep the committed result.
        marker.unlink()
        return
    _switch_link(final, old_final)
    _switch_link(evaluation, old_evaluation)
    marker.unlink()


def metrics(target: np.ndarray, prediction: np.ndarray) -> dict:
    target = np.asarray(target, dtype=np.float64)
    prediction = np.asarray(prediction, dtype=np.float64)
    if (target.ndim != 1 or target.shape != prediction.shape or not len(target)
            or not np.isfinite(target).all() or not np.isfinite(prediction).all()):
        raise ValueError("FuelCast metric arrays differ or contain non-finite values")
    return {"mae": float(mean_absolute_error(target, prediction)),
            "rmse": float(np.sqrt(mean_squared_error(target, prediction))),
            "r2": float(r2_score(target, prediction)) if len(target) >= 2 else None}


def _grouped(target: np.ndarray, prediction: np.ndarray, vessels: np.ndarray) -> dict:
    if vessels.shape != target.shape or set(vessels.tolist()) != set(EXPECTED_CONFIGS):
        raise ValueError("FuelCast vessel coverage mismatch")
    result = {}
    for vessel in EXPECTED_CONFIGS:
        mask = vessels == vessel
        result[vessel] = {"rows": int(mask.sum()), **metrics(target[mask], prediction[mask])}
    return result


def _same_metrics(actual: dict, reported: dict) -> None:
    if set(actual) != set(reported):
        raise ValueError("FuelCast reported metric keys mismatch")
    for key, value in actual.items():
        if value is None:
            if reported[key] is not None:
                raise ValueError("FuelCast reported metric mismatch")
        elif not np.isclose(value, reported[key], rtol=1e-10, atol=1e-12):
            raise ValueError(f"FuelCast reported {key} differs from saved predictions")


def _prediction_file(path: Path, partition) -> np.ndarray:
    with np.load(_regular(path), allow_pickle=False) as source:
        if set(source.files) != {"record_id", "vessel_id", "time_index", "prediction"}:
            raise ValueError("FuelCast validation prediction keys mismatch")
        ids, vessels, times = (source[key] for key in ("record_id", "vessel_id", "time_index"))
        prediction = np.asarray(source["prediction"], dtype=np.float64)
    if (ids.shape != partition.record_id.shape or ids.tolist() != partition.record_id.tolist()
            or vessels.tolist() != partition.vessel_id.tolist()
            or not np.array_equal(times, partition.time_index)
            or prediction.shape != partition.target.shape or not np.isfinite(prediction).all()):
        raise ValueError("FuelCast validation predictions are not identity aligned")
    return prediction


def _candidate_result(name: str, path: Path, split, vqr_split) -> dict:
    manifest_path = _regular(path / "candidate_manifest.json")
    manifest = _json(manifest_path)
    if manifest.get("candidate") != name or manifest.get("mode") != "normal":
        raise ValueError(f"FuelCast {name} is not a normal-mode candidate")
    source = vqr_split if name == "vqr" else split
    loaded = (load_vqr_candidate(path, source) if name == "vqr"
              else load_classical_candidate(path, source))
    if (manifest.get("dataset_id") != DATASET_ID
            or manifest.get("training_rows_full") != len(source.train.target)
            or manifest.get("validation_rows") != len(source.validation.target)
            or manifest.get("partition_counts") != source.partition_counts):
        raise ValueError(f"FuelCast {name} count or provenance mismatch")
    if name == "vqr":
        if manifest.get("benchmark_eligible") is not True:
            raise ValueError("FuelCast VQR is not benchmark eligible")
        reported = _json(path / "validation_metrics.json")
        if (reported.get("validation_rows") != len(source.validation.target)
                or reported.get("benchmark_eligible") is not True):
            raise ValueError("FuelCast VQR metrics report mismatch")
    prediction = _prediction_file(path / "validation_predictions.npz", source.validation)
    actual = metrics(source.validation.target, prediction)
    grouped = _grouped(source.validation.target, prediction, source.validation.vessel_id)
    _same_metrics(actual, manifest["validation_metrics"])
    if set(grouped) != set(manifest["validation_per_vessel"]):
        raise ValueError("FuelCast per-vessel metric coverage mismatch")
    for vessel in EXPECTED_CONFIGS:
        if grouped[vessel]["rows"] != manifest["validation_per_vessel"][vessel]["rows"]:
            raise ValueError("FuelCast per-vessel row count mismatch")
        _same_metrics({k: v for k, v in grouped[vessel].items() if k != "rows"},
                      {k: v for k, v in manifest["validation_per_vessel"][vessel].items() if k != "rows"})
    if name == "vqr":
        _same_metrics(actual, reported["validation_metrics"])
        rebuilt = loaded.predict_angles(source.validation.features)
        if not np.allclose(rebuilt, prediction, rtol=1e-8, atol=1e-9):
            raise ValueError("FuelCast VQR model differs from saved predictions")
    else:
        actual_prediction = loaded.predict(source.validation.features)
        if not np.allclose(actual_prediction, prediction, rtol=1e-10, atol=1e-12):
            raise ValueError("FuelCast classical model differs from saved predictions")
    return {"candidate": name, "model_family": manifest["model_family"],
            "backend": manifest["backend"], "hardware": manifest.get("hardware", "simulator"),
            "validation_rows": len(prediction), "validation_metrics": actual,
            "validation_per_vessel": grouped, "fit_seconds": manifest["fit_seconds"],
            "prediction_seconds": manifest["prediction_seconds"],
            "training_rows_full": manifest["training_rows_full"],
            "training_rows_sampled": manifest["training_rows_sampled"],
            "dependency_versions": manifest["dependency_versions"],
            "candidate_path": str(path), "candidate_manifest_sha256": sha256_file(manifest_path),
            "validation_predictions_sha256": sha256_file(path / "validation_predictions.npz")}


def _source(run_dir: Path, version: str, canonical_sha256: str):
    classical = load_saved_validation(run_dir, version, canonical_sha256)
    quantum = load_saved_vqr_validation(run_dir, version, canonical_sha256)
    if (classical.split_manifest_sha256 != quantum.split_manifest_sha256
            or classical.schema_sha256 != quantum.schema_sha256
            or classical.validation.record_id.tolist() != quantum.validation.record_id.tolist()
            or not np.array_equal(classical.validation.target, quantum.validation.target)):
        raise ValueError("FuelCast classical and VQR validation partitions differ")
    return classical, quantum


def _rank_candidates(results: list[dict]) -> list[dict]:
    if len(results) != 5 or {row["candidate"] for row in results} != set((*CANDIDATES, "vqr")):
        raise ValueError("FuelCast eligible candidate field is incomplete")
    return sorted(results, key=lambda row: (row["validation_metrics"]["mae"], row["candidate"]))


def select_fuelcast_champion(run_dir: Path, expected_version: str,
                             expected_canonical_sha256: str) -> dict:
    """Freeze normal-mode validation winner without reading test.npz."""
    run_dir = Path(run_dir).resolve(strict=True)
    evaluation = run_dir / "07_evaluation"
    final = run_dir.parent / "final_model"
    if os.path.lexists(evaluation) or os.path.lexists(final):
        raise FileExistsError("FuelCast selection or final package already exists")
    split, vqr_split = _source(run_dir, expected_version, expected_canonical_sha256)
    paths = {name: run_dir / "05_classical" / "normal" / name for name in CANDIDATES}
    paths["vqr"] = run_dir / "06_quantum" / "vqr" / "normal" / "candidate"
    results = [_candidate_result(name, paths[name], split, vqr_split) for name in (*CANDIDATES, "vqr")]
    results = _rank_candidates(results)
    winner = results[0]
    candidate_path = paths[winner["candidate"]]
    candidate_manifest = _json(candidate_path / "candidate_manifest.json")
    selection = {"run_id": run_dir.name, "dataset_id": DATASET_ID,
                 "dataset_version": expected_version, "canonical_sha256": expected_canonical_sha256,
                 "split_manifest_sha256": split.split_manifest_sha256,
                 "feature_schema_sha256": split.schema_sha256,
                 "selection_metric": "validation_mae", "refit": False,
                 "champion_model": winner["candidate"], "model_family": winner["model_family"],
                 "candidate_manifest_sha256": winner["candidate_manifest_sha256"],
                 "candidate_artifact_sha256": candidate_manifest["artifact_sha256"],
                 "validation_rows": len(split.validation.target),
                 "leaderboard": results}
    final_tmp = Path(tempfile.mkdtemp(prefix=".final_model-", dir=run_dir.parent))
    evaluation_tmp = Path(tempfile.mkdtemp(prefix=".07_evaluation-", dir=run_dir))
    published_final = False
    try:
        shutil.copytree(candidate_path, final_tmp / "model", symlinks=False)
        preprocessor_name = ("vqr_preprocessor.pkl" if winner["candidate"] == "vqr"
                             else "preprocessor.pkl")
        shutil.copyfile(run_dir / "04_transformation" / preprocessor_name,
                        final_tmp / "preprocessor.pkl")
        shutil.copyfile(run_dir / "04_transformation" / "feature_schema.json",
                        final_tmp / "feature_schema.json")
        package_files = {"preprocessor.pkl": sha256_file(final_tmp / "preprocessor.pkl"),
                         "feature_schema.json": sha256_file(final_tmp / "feature_schema.json")}
        for name in candidate_manifest["artifact_sha256"]:
            package_files[f"model/{name}"] = sha256_file(final_tmp / "model" / name)
        package_files["model/candidate_manifest.json"] = sha256_file(final_tmp / "model" / "candidate_manifest.json")
        model_manifest = {"champion_model": winner["candidate"], "model_family": winner["model_family"],
                          "backend": winner["backend"], "hardware": winner["hardware"],
                          "selection_metric": "validation_mae", "refit": False,
                          "dataset_id": DATASET_ID, "dataset_version": expected_version,
                          "canonical_sha256": expected_canonical_sha256,
                          "split_manifest_sha256": split.split_manifest_sha256,
                          "target": CANONICAL_TARGET, "raw_features": list(CANONICAL_FEATURES),
                          "run_id": run_dir.name, "candidate_manifest_sha256": winner["candidate_manifest_sha256"],
                          "dependency_versions": winner["dependency_versions"],
                          "artifact_sha256": package_files, "test_metrics": None}
        _write(final_tmp / "leaderboard.json", {"selection_metric": "validation_mae", "candidates": results})
        package_files["leaderboard.json"] = sha256_file(final_tmp / "leaderboard.json")
        _write(final_tmp / "model_manifest.json", model_manifest)
        _write(evaluation_tmp / "leaderboard.json", {"selection_metric": "validation_mae", "candidates": results})
        selection["final_package_sha256"] = {name: sha256_file(final_tmp / name) for name in
                                            ("model_manifest.json", "leaderboard.json")}
        _write(evaluation_tmp / "selection_manifest.json", selection)
        _switch_link(final, final_tmp)
        published_final = True
        _switch_link(evaluation, evaluation_tmp)
    except BaseException:
        if published_final:
            final.unlink()
        shutil.rmtree(final_tmp, ignore_errors=True)
        shutil.rmtree(evaluation_tmp, ignore_errors=True)
        raise
    return selection


@dataclass
class FinalModel:
    loaded: object
    preprocessor: object
    manifest: dict

    def predict(self, canonical_features: pd.DataFrame) -> np.ndarray:
        if (not isinstance(canonical_features, pd.DataFrame)
                or list(canonical_features.columns) != list(CANONICAL_FEATURES)):
            raise ValueError("FuelCast inference requires six ordered raw canonical columns")
        raw = canonical_features.to_numpy(dtype=np.float64)
        if raw.ndim != 2 or np.isinf(raw).any():
            raise ValueError("FuelCast raw features contain infinity")
        if self.manifest["champion_model"] == "vqr":
            return self.loaded.predict(canonical_features)
        transformed = self.preprocessor.transform(raw)
        return self.loaded.predict(pd.DataFrame(transformed, columns=CLASSICAL_FEATURES))

    def predict_saved(self, features: pd.DataFrame) -> np.ndarray:
        if self.manifest["champion_model"] == "vqr":
            return self.loaded.predict_angles(features)
        return self.loaded.predict(features)


def load_final_model(model_dir: Path) -> FinalModel:
    """Validate package hashes and dependency versions, then reconstruct inference."""
    model_dir = Path(model_dir).resolve(strict=True)
    manifest = _json(_regular(model_dir / "model_manifest.json"))
    schema = _json(_regular(model_dir / "feature_schema.json"))
    if (manifest.get("dataset_id") != DATASET_ID or manifest.get("target") != CANONICAL_TARGET
            or manifest.get("raw_features") != list(CANONICAL_FEATURES)
            or schema.get("raw_features") != list(CANONICAL_FEATURES)
            or schema.get("dataset_version") != manifest.get("dataset_version")
            or manifest.get("selection_metric") != "validation_mae"
            or manifest.get("refit") is not False):
        raise ValueError("FuelCast final model schema or policy mismatch")
    candidate_dir = model_dir / "model"
    candidate_manifest = _json(_regular(candidate_dir / "candidate_manifest.json"))
    if (candidate_manifest.get("candidate") != manifest.get("champion_model")
            or candidate_manifest.get("model_family") != manifest.get("model_family")
            or candidate_manifest.get("backend") != manifest.get("backend")
            or candidate_manifest.get("run_id") != manifest.get("run_id")
            or candidate_manifest.get("dataset_version") != manifest.get("dataset_version")
            or candidate_manifest.get("canonical_sha256") != manifest.get("canonical_sha256")
            or candidate_manifest.get("split_manifest_sha256") != manifest.get("split_manifest_sha256")
            or candidate_manifest.get("dependency_versions") != manifest.get("dependency_versions")):
        raise ValueError("FuelCast final model candidate identity mismatch")
    hashes = manifest.get("artifact_sha256", {})
    expected = {"preprocessor.pkl", "feature_schema.json", "leaderboard.json",
                "model/candidate_manifest.json"}
    expected.update(f"model/{name}" for name in candidate_manifest.get("artifact_sha256", {}))
    if manifest.get("test_metrics") is not None:
        expected.add("metrics.json")
    if set(hashes) != expected:
        raise ValueError("FuelCast final package artifact set mismatch")
    for name, digest in hashes.items():
        path = _regular(model_dir / name)
        if path.resolve(strict=True) != model_dir / name or sha256_file(path) != digest:
            raise ValueError(f"FuelCast final package {name} hash mismatch")
    if hashes["model/candidate_manifest.json"] != manifest.get("candidate_manifest_sha256"):
        raise ValueError("FuelCast final candidate manifest hash mismatch")
    board = _json(model_dir / "leaderboard.json")
    if (board.get("selection_metric") != "validation_mae"
            or len(board.get("candidates", [])) != 5
            or board["candidates"][0]["candidate"] != manifest["champion_model"]):
        raise ValueError("FuelCast final leaderboard mismatch")
    if manifest.get("test_metrics") is not None:
        report = _json(model_dir / "metrics.json")
        if (report.get("champion_model") != manifest["champion_model"]
                or report.get("test_metrics") != manifest["test_metrics"]
                or report.get("test_per_vessel") != manifest.get("test_per_vessel")):
            raise ValueError("FuelCast final test report mismatch")
    if (hashes["feature_schema.json"] != candidate_manifest["feature_schema_sha256"]
            or hashes["preprocessor.pkl"] != candidate_manifest["phase4_artifact_sha256"]["vqr_preprocessor.pkl" if manifest["champion_model"] == "vqr" else "preprocessor.pkl"]):
        raise ValueError("FuelCast final preprocessing provenance mismatch")
    preprocessor = joblib.load(model_dir / "preprocessor.pkl")
    if manifest["champion_model"] == "vqr":
        loaded = load_vqr_candidate(candidate_dir)
    elif manifest["champion_model"] in CANDIDATES:
        source = SimpleNamespace(run_dir=Path(manifest["run_id"]),
                                 dataset_version=manifest["dataset_version"],
                                 canonical_sha256=manifest["canonical_sha256"],
                                 schema_sha256=hashes["feature_schema.json"],
                                 split_manifest_sha256=manifest["split_manifest_sha256"],
                                 source_hashes=candidate_manifest["phase4_artifact_sha256"])
        loaded = load_classical_candidate(candidate_dir, source)
    else:
        raise ValueError("Unknown FuelCast final candidate")
    return FinalModel(loaded, preprocessor, manifest)


def load_saved_test(run_dir: Path, selection: dict):
    """Open only the frozen test partition and check hashes, rows, and boundaries."""
    run_dir = Path(run_dir).resolve(strict=True)
    stage = run_dir / "04_transformation"
    split_path = _regular(stage / "split_manifest.json")
    if sha256_file(split_path) != selection["split_manifest_sha256"]:
        raise ValueError("FuelCast frozen split manifest changed")
    split = _json(split_path)
    schema_path = _regular(stage / "feature_schema.json")
    schema = _json(schema_path)
    if (sha256_file(schema_path) != selection["feature_schema_sha256"]
            or split.get("dataset_version") != selection["dataset_version"]
            or split.get("canonical_sha256") != selection["canonical_sha256"]
            or schema.get("raw_features") != list(CANONICAL_FEATURES)):
        raise ValueError("FuelCast frozen schema or provenance changed")
    test_path = _regular(stage / "test.npz")
    if sha256_file(test_path) != split.get("artifact_sha256", {}).get("test.npz"):
        raise ValueError("FuelCast test partition hash mismatch")
    with np.load(test_path, allow_pickle=False) as source:
        if set(source.files) != set(schema["array_keys"]):
            raise ValueError("FuelCast test array keys mismatch")
        arrays = {name: source[name] for name in source.files}
    n = split["partition_counts"]["test"]
    if (arrays["features"].shape != (n, len(CLASSICAL_FEATURES))
            or arrays["vqr_features"].shape != (n, len(CANONICAL_FEATURES))
            or any(arrays[name].shape != (n,) for name in
                   ("target", "vqr_target", "record_id", "vessel_id", "time_index"))
            or not all(np.isfinite(arrays[name]).all() for name in
                       ("features", "vqr_features", "target", "vqr_target"))
            or (arrays["target"] < 0).any()
            or not np.issubdtype(arrays["time_index"].dtype, np.integer)):
        raise ValueError("FuelCast test arrays have invalid shape or values")
    expected_ids = []
    cursor = 0
    for vessel in EXPECTED_CONFIGS:
        parts = split["per_vessel"][vessel]
        detail = parts["test"]
        count = detail["count"]
        selected = slice(cursor, cursor + count)
        times = arrays["time_index"][selected]
        if (count <= 0 or len(times) != count
                or not np.all(arrays["vessel_id"][selected] == vessel)
                or int(times[0]) != detail["first_time_index"]
                or int(times[-1]) != detail["last_time_index"]
                or np.any(np.diff(times) <= 0)
                or parts["train"]["last_time_index"] >= parts["validation"]["first_time_index"]
                or parts["validation"]["last_time_index"] >= detail["first_time_index"]):
            raise ValueError("FuelCast test vessel/time boundary mismatch")
        expected_ids.extend(detail["record_ids"])
        cursor += count
    train_validation_ids = {record_id for vessel in EXPECTED_CONFIGS
                            for part in ("train", "validation")
                            for record_id in split["per_vessel"][vessel][part]["record_ids"]}
    if (cursor != n or arrays["record_id"].tolist() != expected_ids
            or len(set(expected_ids)) != n or train_validation_ids.intersection(expected_ids)):
        raise ValueError("FuelCast test row identities overlap or differ")
    return arrays


def evaluate_frozen_champion(run_dir: Path) -> dict:
    """Evaluate the frozen package once; publish results only after all checks."""
    run_dir = Path(run_dir).resolve(strict=True)
    _recover_transaction(run_dir)
    evaluation = run_dir / "07_evaluation"
    selection_path = _regular(evaluation / "selection_manifest.json")
    selection = _json(selection_path)
    if any(os.path.lexists(evaluation / name) for name in
           ("test_predictions.npz", "metrics.json", "evaluation_manifest.json")):
        raise FileExistsError("FuelCast final test has already been evaluated")
    model_dir = run_dir.parent / "final_model"
    for name, digest in selection["final_package_sha256"].items():
        if sha256_file(_regular(model_dir / name)) != digest:
            raise ValueError("FuelCast frozen package changed before test")
    package = load_final_model(model_dir)
    if (selection["champion_model"] != package.manifest["champion_model"]
            or selection["candidate_manifest_sha256"] != package.manifest["candidate_manifest_sha256"]
            or selection["run_id"] != run_dir.name
            or selection["dataset_id"] != package.manifest["dataset_id"]
            or selection["dataset_version"] != package.manifest["dataset_version"]
            or selection["canonical_sha256"] != package.manifest["canonical_sha256"]
            or selection["split_manifest_sha256"] != package.manifest["split_manifest_sha256"]
            or selection["model_family"] != package.manifest["model_family"]
            or selection["candidate_artifact_sha256"] !=
               _json(model_dir / "model" / "candidate_manifest.json")["artifact_sha256"]
            or selection["leaderboard"] != _json(evaluation / "leaderboard.json")["candidates"]
            or selection["leaderboard"] != _json(model_dir / "leaderboard.json")["candidates"]):
        raise ValueError("FuelCast frozen champion identity changed")
    test = load_saved_test(run_dir, selection)
    feature_name = "vqr_features" if selection["champion_model"] == "vqr" else "features"
    columns = CANONICAL_FEATURES if feature_name == "vqr_features" else CLASSICAL_FEATURES
    start = time.perf_counter()
    prediction = package.predict_saved(pd.DataFrame(test[feature_name], columns=columns))
    duration = time.perf_counter() - start
    overall = metrics(test["target"], prediction)
    by_vessel = _grouped(test["target"], prediction, test["vessel_id"])
    report = {"champion_model": selection["champion_model"], "model_family": selection["model_family"],
              "test_rows": len(prediction), "test_metrics": overall,
              "test_per_vessel": by_vessel, "prediction_seconds": duration}
    staging = Path(tempfile.mkdtemp(prefix=".phase8-test-", dir=run_dir))
    try:
        np.savez_compressed(staging / "test_predictions.npz",
                            record_id=test["record_id"], vessel_id=test["vessel_id"],
                            time_index=test["time_index"], target=test["target"],
                            prediction=prediction)
        _write(staging / "metrics.json", report)
        evaluation_manifest = {"run_id": run_dir.name,
                               "selection_manifest_sha256": sha256_file(selection_path),
                               "champion_model": selection["champion_model"],
                               "candidate_manifest_sha256": selection["candidate_manifest_sha256"],
                               "test_rows": len(prediction),
                               "artifact_sha256": {name: sha256_file(staging / name) for name in
                                                   ("test_predictions.npz", "metrics.json")}}
        _write(staging / "evaluation_manifest.json", evaluation_manifest)
        final_manifest = dict(package.manifest)
        final_manifest["test_metrics"] = overall
        final_manifest["test_per_vessel"] = by_vessel
        final_manifest["test_prediction_seconds"] = duration
        final_manifest["evaluation_manifest_sha256"] = sha256_file(staging / "evaluation_manifest.json")
        final_manifest["artifact_sha256"] = {**final_manifest["artifact_sha256"],
                                             "metrics.json": sha256_file(staging / "metrics.json")}
        _write(staging / "model_manifest.json", final_manifest)
        _write(staging / "leaderboard.json", _json(model_dir / "leaderboard.json"))
        # Build both complete destinations before changing either public pointer.
        updated = Path(tempfile.mkdtemp(prefix=".final_model-evaluated-", dir=run_dir.parent))
        updated_evaluation = Path(tempfile.mkdtemp(prefix=".07_evaluation-evaluated-", dir=run_dir))
        try:
            shutil.copytree(model_dir / "model", updated / "model")
            for name in ("preprocessor.pkl", "feature_schema.json"):
                shutil.copyfile(model_dir / name, updated / name)
            for name in ("model_manifest.json", "leaderboard.json"):
                shutil.copyfile(staging / name, updated / name)
            shutil.copyfile(staging / "metrics.json", updated / "metrics.json")
            for name in ("selection_manifest.json", "leaderboard.json"):
                shutil.copyfile(evaluation / name, updated_evaluation / name)
            for name in ("test_predictions.npz", "metrics.json", "evaluation_manifest.json"):
                shutil.copyfile(staging / name, updated_evaluation / name)
            if not model_dir.is_symlink() or not evaluation.is_symlink():
                raise ValueError("FuelCast Phase 8 outputs must use atomic publication links")
            marker = run_dir / ".phase8-evaluation-transaction.json"
            if marker.exists():
                raise FileExistsError("FuelCast evaluation transaction already exists")
            _write(marker, {"old_final": os.readlink(model_dir),
                            "old_evaluation": os.readlink(evaluation),
                            "new_final": updated.name,
                            "new_evaluation": updated_evaluation.name})
            try:
                _switch_link(model_dir, updated)
                _switch_link(evaluation, updated_evaluation)
                marker.unlink()
            except BaseException:
                _recover_transaction(run_dir)
                raise
        finally:
            if not (model_dir.is_symlink() and model_dir.resolve() == updated):
                shutil.rmtree(updated, ignore_errors=True)
            if not (evaluation.is_symlink() and evaluation.resolve() == updated_evaluation):
                shutil.rmtree(updated_evaluation, ignore_errors=True)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Select and evaluate a frozen FuelCast champion")
    commands = parser.add_subparsers(dest="command", required=True)
    select = commands.add_parser("select", help="validate normal candidates and freeze validation winner")
    select.add_argument("--run-dir", type=Path, required=True)
    select.add_argument("--expected-version", required=True)
    select.add_argument("--expected-canonical-sha256", required=True)
    evaluate = commands.add_parser("evaluate", help="score frozen champion once on saved test")
    evaluate.add_argument("--run-dir", type=Path, required=True)
    verify = commands.add_parser("verify", help="load final package and predict one raw canonical row")
    verify.add_argument("--model-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "select":
        result = select_fuelcast_champion(args.run_dir, args.expected_version,
                                           args.expected_canonical_sha256)
        print(f"Frozen {result['champion_model']} on validation MAE")
    elif args.command == "evaluate":
        result = evaluate_frozen_champion(args.run_dir)
        print(json.dumps(result, indent=2))
    else:
        loaded = load_final_model(args.model_dir)
        sample = pd.DataFrame([[5.0, 8.0, 180.0, 1.5, 8.0, 0.5]], columns=CANONICAL_FEATURES)
        print(f"Verified {loaded.manifest['champion_model']}: {float(loaded.predict(sample)[0])} kg/s")


if __name__ == "__main__":
    main()
