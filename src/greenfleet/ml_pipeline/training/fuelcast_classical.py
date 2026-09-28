"""Bounded classical FuelCast tuning on the saved validation partition."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import ParameterGrid, ParameterSampler

from greenfleet.artifacts.fuelcast_classical_artifact import FuelCastClassicalArtifact
from greenfleet.config.fuelcast_classical_config import FuelCastClassicalConfig
from greenfleet.constants.fuelcast import DATASET_ID, EXPECTED_CONFIGS
from greenfleet.constants.fuelcast_classical import (
    CANDIDATES, CLASSICAL_FEATURES, QUICK_ROWS_PER_VESSEL, SEARCHES,
)
from greenfleet.ml_pipeline.training.fuelcast_classical_model import load_classical_candidate
from greenfleet.ml_pipeline.training.fuelcast_data import (
    SavedValidationSplit, load_saved_validation, sha256_file,
)


def _xgboost():
    try:
        import xgboost
    except Exception as exc:
        raise RuntimeError(
            "XGBoost is required; install with python -m pip install -r requirements.txt "
            "and ensure the OpenMP runtime (libomp on macOS) is available"
        ) from exc
    return xgboost


def _estimator(name: str, parameters: dict, seed: int):
    if name == "ridge":
        return Ridge(solver="svd", **parameters)
    if name == "random_forest":
        return RandomForestRegressor(random_state=seed, n_jobs=2, **parameters)
    if name == "gradient_boosting":
        return GradientBoostingRegressor(random_state=seed, **parameters)
    if name == "xgboost":
        return _xgboost().XGBRegressor(
            random_state=seed, n_jobs=2, objective="reg:squarederror",
            tree_method="hist", **parameters,
        )
    raise ValueError(f"Unknown FuelCast candidate: {name}")


def _metrics(target: np.ndarray, predictions: np.ndarray) -> dict[str, float | None]:
    return {
        "mae": float(mean_absolute_error(target, predictions)),
        "rmse": float(np.sqrt(mean_squared_error(target, predictions))),
        "r2": float(r2_score(target, predictions)) if len(target) >= 2 else None,
    }


def _sample_training(split: SavedValidationSplit, mode: str) -> np.ndarray:
    if mode == "normal":
        return np.arange(len(split.train.target), dtype=np.int64)
    chunks = []
    for vessel in EXPECTED_CONFIGS:
        positions = np.flatnonzero(split.train.vessel_id == vessel)
        count = min(len(positions), QUICK_ROWS_PER_VESSEL)
        if count == 0:
            raise ValueError(f"FuelCast training partition lacks {vessel}")
        selected = np.linspace(0, len(positions) - 1, num=count, dtype=np.int64)
        chunks.append(positions[selected])
    return np.sort(np.concatenate(chunks))


def _configuration_key(parameters: dict) -> str:
    return json.dumps(parameters, sort_keys=True, separators=(",", ":"))


def _dependency_versions(name: str) -> dict[str, str]:
    versions = {
        "python": platform.python_version(), "numpy": np.__version__,
        "pandas": pd.__version__, "scikit_learn": sklearn.__version__,
        "joblib": joblib.__version__,
    }
    if name == "xgboost":
        versions["xgboost"] = _xgboost().__version__
    return versions


def _save_candidate(
    name: str, split: SavedValidationSplit, indices: np.ndarray,
    config: FuelCastClassicalConfig, output: Path,
) -> FuelCastClassicalArtifact:
    output.mkdir()
    method, space, budget = SEARCHES[config.mode][name]
    configurations = (list(ParameterGrid(space)) if method == "grid"
                      else list(ParameterSampler(space, n_iter=budget, random_state=config.seed)))
    if len(configurations) != budget:
        raise ValueError(f"FuelCast {name} search budget mismatch")
    x_train = split.train.features.iloc[indices]
    y_train = split.train.target[indices]
    x_validation = split.validation.features
    y_validation = split.validation.target
    trials = []
    for parameters in configurations:
        model = _estimator(name, parameters, config.seed)
        start = time.perf_counter()
        model.fit(x_train, y_train)
        fit_seconds = time.perf_counter() - start
        start = time.perf_counter()
        predictions = np.asarray(model.predict(x_validation), dtype=np.float64)
        predict_seconds = time.perf_counter() - start
        if predictions.shape != y_validation.shape or not np.isfinite(predictions).all():
            raise ValueError(f"FuelCast {name} returned invalid search predictions")
        mae = float(mean_absolute_error(y_validation, predictions))
        trials.append({
            "parameters": parameters, "validation_mae": mae,
            "fit_seconds": fit_seconds, "prediction_seconds": predict_seconds,
        })
    best = min(trials, key=lambda trial: (trial["validation_mae"], _configuration_key(trial["parameters"])))
    best_parameters = best["parameters"]
    final_model = _estimator(name, best_parameters, config.seed)
    start = time.perf_counter()
    final_model.fit(x_train, y_train)
    fit_seconds = time.perf_counter() - start
    start = time.perf_counter()
    prediction = np.asarray(final_model.predict(x_validation), dtype=np.float64).reshape(-1)
    prediction_seconds = time.perf_counter() - start
    if prediction.shape != y_validation.shape or not np.isfinite(prediction).all():
        raise ValueError(f"FuelCast {name} returned invalid validation predictions")
    overall = _metrics(y_validation, prediction)
    by_vessel = {}
    for vessel in EXPECTED_CONFIGS:
        mask = split.validation.vessel_id == vessel
        by_vessel[vessel] = {"rows": int(mask.sum()), **_metrics(y_validation[mask], prediction[mask])}
    model_file = "model.json" if name == "xgboost" else "model.joblib"
    model_path = output / model_file
    if name == "xgboost":
        final_model.save_model(model_path)
    else:
        joblib.dump(final_model, model_path)
    predictions_path = output / "validation_predictions.npz"
    np.savez_compressed(
        predictions_path, record_id=split.validation.record_id,
        vessel_id=split.validation.vessel_id, time_index=split.validation.time_index,
        prediction=prediction,
    )
    results_path = output / "search_results.json"
    results_path.write_text(json.dumps({
        "search_method": method, "search_space": space, "n_iter": budget,
        "seed": config.seed, "trials": trials,
    }, indent=2) + "\n", encoding="utf-8")
    sampled_ids = split.train.record_id[indices].tolist() if config.mode == "quick" else []
    sampled_counts = {vessel: int(np.count_nonzero(split.train.vessel_id[indices] == vessel))
                      for vessel in EXPECTED_CONFIGS}
    manifest = {
        "candidate": name, "model_family": "classical", "backend": "cpu",
        "hardware": "classical", "model_file": model_file,
        "serialization": "xgboost_json" if name == "xgboost" else "joblib",
        "dataset_id": DATASET_ID, "dataset_version": split.dataset_version,
        "canonical_sha256": split.canonical_sha256, "run_id": split.run_dir.name,
        "feature_order": list(CLASSICAL_FEATURES),
        "feature_schema_sha256": split.schema_sha256,
        "split_manifest_sha256": split.split_manifest_sha256,
        "phase4_artifact_sha256": split.source_hashes,
        "target": "fuel_consumption_kg_s", "target_unit": "kg/s",
        "mode": config.mode, "seed": config.seed,
        "training_rows_full": len(split.train.target), "training_rows_sampled": len(indices),
        "training_sample_counts": sampled_counts, "training_sample_record_ids": sampled_ids,
        "validation_rows": len(y_validation), "partition_counts": split.partition_counts,
        "search_method": method, "search_space": space, "n_iter": budget,
        "tried_configurations": [trial["parameters"] for trial in trials],
        "best_parameters": best_parameters, "validation_metrics": overall,
        "validation_per_vessel": by_vessel,
        "search_fit_seconds": float(sum(trial["fit_seconds"] for trial in trials)),
        "fit_seconds": fit_seconds, "prediction_seconds": prediction_seconds,
        "dependency_versions": _dependency_versions(name),
        "artifact_sha256": {path.name: sha256_file(path)
                            for path in (model_path, predictions_path, results_path)},
    }
    manifest_path = output / "candidate_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return FuelCastClassicalArtifact(output, manifest_path, results_path, predictions_path, model_path)


def verify_candidate(run_dir: Path, candidate_dir: Path) -> dict:
    manifest = json.loads((candidate_dir / "candidate_manifest.json").read_text(encoding="utf-8"))
    split = load_saved_validation(
        run_dir, manifest["dataset_version"], manifest["canonical_sha256"],
    )
    loaded = load_classical_candidate(candidate_dir, split)
    with np.load(candidate_dir / "validation_predictions.npz", allow_pickle=False) as stored:
        if set(stored.files) != {"record_id", "vessel_id", "time_index", "prediction"}:
            raise ValueError("FuelCast saved validation predictions schema mismatch")
        if (stored["record_id"].tolist() != split.validation.record_id.tolist()
                or stored["vessel_id"].tolist() != split.validation.vessel_id.tolist()
                or not np.array_equal(stored["time_index"], split.validation.time_index)):
            raise ValueError("FuelCast saved validation prediction identities mismatch")
        expected = stored["prediction"]
    actual = loaded.predict(split.validation.features)
    if not np.allclose(actual, expected, rtol=1e-10, atol=1e-12):
        raise ValueError("FuelCast fresh-load predictions differ")
    actual_metrics = _metrics(split.validation.target, actual)
    for key, value in actual_metrics.items():
        if not np.isclose(value, manifest["validation_metrics"][key], rtol=1e-10, atol=1e-12):
            raise ValueError("FuelCast fresh-load metrics differ")
    return manifest


def train_classical(config: FuelCastClassicalConfig) -> Path:
    split = load_saved_validation(
        config.run_dir, config.expected_version, config.expected_canonical_sha256,
    )
    _xgboost()  # Fail before any candidate is published if the required family is unavailable.
    selected = _sample_training(split, config.mode)
    root = split.run_dir / "05_classical"
    root.mkdir(exist_ok=True)
    published = root / config.mode
    if os.path.lexists(published):
        raise FileExistsError(f"FuelCast classical mode already published: {published}")
    staging = Path(tempfile.mkdtemp(prefix=f".{config.mode}-staging-", dir=root))
    try:
        entries = []
        for name in CANDIDATES:
            artifact = _save_candidate(name, split, selected, config, staging / name)
            try:
                subprocess.run([
                    sys.executable, "-m", "greenfleet.ml_pipeline.training.fuelcast_classical",
                    "verify", "--run-dir", str(split.run_dir),
                    "--candidate-dir", str(artifact.candidate_dir),
                ], check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as exc:
                raise RuntimeError(
                    f"FuelCast {name} fresh-process verification failed: {exc.stderr.strip()}"
                ) from exc
            manifest = json.loads(artifact.manifest_path.read_text(encoding="utf-8"))
            entries.append({
                "candidate": name, "manifest_path": f"{name}/candidate_manifest.json",
                "validation_metrics": manifest["validation_metrics"],
                "validation_per_vessel": manifest["validation_per_vessel"],
            })
        entries.sort(key=lambda item: (item["validation_metrics"]["mae"], item["candidate"]))
        for rank, entry in enumerate(entries, start=1):
            entry["rank"] = rank
        leaderboard = {
            "run_id": split.run_dir.name, "dataset_id": DATASET_ID,
            "dataset_version": split.dataset_version,
            "canonical_sha256": split.canonical_sha256,
            "mode": config.mode, "selection_scope": "classical_validation_only",
            "selection_metric": "validation_mae", "candidates": entries,
        }
        (staging / "classical_leaderboard.json").write_text(
            json.dumps(leaderboard, indent=2) + "\n", encoding="utf-8",
        )
        os.replace(staging, published)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return published


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Tune or verify FuelCast classical candidates")
    commands = parser.add_subparsers(dest="command", required=True)
    train = commands.add_parser("train")
    train.add_argument("--run-dir", type=Path, required=True)
    train.add_argument("--mode", choices=tuple(SEARCHES), required=True)
    train.add_argument("--expected-version", required=True)
    train.add_argument("--expected-canonical-sha256", required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("--run-dir", type=Path, required=True)
    verify.add_argument("--candidate-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "train":
        result = train_classical(FuelCastClassicalConfig(
            args.run_dir, args.mode, args.expected_version,
            args.expected_canonical_sha256,
        ))
        print(f"FuelCast classical leaderboard: {result / 'classical_leaderboard.json'}")
    else:
        result = verify_candidate(args.run_dir, args.candidate_dir)
        print(f"Verified FuelCast candidate: {result['candidate']}")


if __name__ == "__main__":
    main()
