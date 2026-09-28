"""Simulator-based FuelCast VQR on saved chronological training/validation rows."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

import joblib
import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from greenfleet.artifacts.fuelcast_vqr_artifact import FuelCastVQRArtifact
from greenfleet.config.fuelcast_vqr_config import FuelCastVQRConfig
from greenfleet.constants.fuelcast import DATASET_ID, EXPECTED_CONFIGS
from greenfleet.constants.fuelcast_vqr import (
    VQR_BATCH_SIZE, VQR_FEATURES, VQR_MODES, VQR_TARGET,
    VQR_VALIDATION_WALL_SECONDS,
)
from greenfleet.ml_pipeline.quantum.fuelcast_vqr_data import (
    SavedVQRValidation, load_saved_vqr_validation,
)
from greenfleet.ml_pipeline.quantum.fuelcast_vqr_model import (
    build_vqr_circuits, circuit_configuration, dependency_versions,
    load_vqr_candidate, quantum_dependencies,
)
from greenfleet.ml_pipeline.training.fuelcast_data import sha256_file


def _write_json_atomic(path: Path, value: object) -> None:
    staged = path.with_name(path.name + ".tmp")
    staged.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    os.replace(staged, path)


def _metrics(target: np.ndarray, prediction: np.ndarray) -> dict[str, float | None]:
    return {
        "mae": float(mean_absolute_error(target, prediction)),
        "rmse": float(np.sqrt(mean_squared_error(target, prediction))),
        "r2": float(r2_score(target, prediction)) if len(target) >= 2 else None,
    }


def sample_training(split: SavedVQRValidation, requested: int, seed: int = 42) -> tuple[np.ndarray, dict]:
    """Proportional allocation, then evenly spaced rows within each vessel."""
    counts = {v: int(np.count_nonzero(split.train.vessel_id == v)) for v in EXPECTED_CONFIGS}
    if any(count == 0 for count in counts.values()):
        raise ValueError("FuelCast VQR training sample requires all three vessels")
    total = sum(counts.values())
    sample_size = min(requested, total)
    if sample_size < len(EXPECTED_CONFIGS):
        raise ValueError("FuelCast VQR training sample is too small")
    quotas = {v: sample_size * counts[v] / total for v in EXPECTED_CONFIGS}
    allocation = {v: min(counts[v], max(1, int(np.floor(quotas[v]))))
                  for v in EXPECTED_CONFIGS}
    while sum(allocation.values()) < sample_size:
        eligible = [v for v in EXPECTED_CONFIGS if allocation[v] < counts[v]]
        selected = max(eligible, key=lambda v: (quotas[v] - allocation[v], -EXPECTED_CONFIGS.index(v)))
        allocation[selected] += 1
    while sum(allocation.values()) > sample_size:
        eligible = [v for v in EXPECTED_CONFIGS if allocation[v] > 1]
        selected = min(eligible, key=lambda v: (quotas[v] - allocation[v], EXPECTED_CONFIGS.index(v)))
        allocation[selected] -= 1
    positions = []
    for vessel in EXPECTED_CONFIGS:
        vessel_positions = np.flatnonzero(split.train.vessel_id == vessel)
        offsets = np.linspace(0, len(vessel_positions) - 1,
                              num=allocation[vessel], dtype=np.int64)
        positions.append(vessel_positions[offsets])
    selected = np.sort(np.concatenate(positions))
    if len(selected) != sample_size or len(np.unique(selected)) != sample_size:
        raise ValueError("FuelCast VQR training sample identities are not unique")
    sample = {
        "selection_algorithm": "proportional_largest_remainder_then_time_spaced_linspace",
        "seed": seed, "requested_rows": requested, "training_rows_full": total,
        "training_rows_sampled": sample_size, "per_vessel_full": counts,
        "per_vessel_sampled": allocation,
        "record_ids": split.train.record_id[selected].tolist(),
        "vessel_ids": split.train.vessel_id[selected].tolist(),
        "time_indexes": split.train.time_index[selected].astype(int).tolist(),
    }
    return selected, sample


def _validate_saved_scalers(split: SavedVQRValidation):
    angle_preprocessor = joblib.load(split.preprocessor_path)
    target_scaler = joblib.load(split.target_scaler_path)
    if (getattr(target_scaler, "feature_range", None) != (-1, 1)
            or target_scaler.data_max_[0] <= target_scaler.data_min_[0]):
        raise ValueError("FuelCast VQR target scaler must be training-fitted and nondegenerate")
    for name in ("train", "validation"):
        part = getattr(split, name)
        expected = target_scaler.transform(part.target.reshape(-1, 1)).reshape(-1)
        if not np.allclose(expected, part.scaled_target, rtol=1e-12, atol=1e-12):
            raise ValueError(f"FuelCast VQR {name} saved target scaling mismatch")
    return angle_preprocessor, target_scaler


def _sample_digest(sample: dict) -> str:
    payload = json.dumps(sample["record_ids"], separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _restart_point(
    checkpoint: Path | None, split: SavedVQRValidation, sample: dict,
    mode: str, seed: int, default: np.ndarray,
) -> tuple[np.ndarray, str | None]:
    """Start a new COBYLA attempt from a prior best loss, never restore optimizer state."""
    if checkpoint is None:
        return default, None
    checkpoint = checkpoint.resolve(strict=True)
    paths = [checkpoint / name for name in
             ("attempt_manifest.json", "sample_manifest.json", "optimizer_history.json")]
    if any(path.is_symlink() or not path.is_file() or path.resolve().parent != checkpoint
           for path in paths):
        raise ValueError("FuelCast VQR restart files must be regular checkpoint files")
    previous = json.loads(paths[0].read_text(encoding="utf-8"))
    old_sample = json.loads(paths[1].read_text(encoding="utf-8"))
    history = json.loads(paths[2].read_text(encoding="utf-8"))
    if (previous.get("run_id") != split.run_dir.name
            or previous.get("dataset_version") != split.dataset_version
            or previous.get("canonical_sha256") != split.canonical_sha256
            or previous.get("feature_schema_sha256") != split.schema_sha256
            or previous.get("split_manifest_sha256") != split.split_manifest_sha256
            or previous.get("mode") != mode or previous.get("seed") != seed
            or previous.get("sample_record_ids_sha256") != _sample_digest(sample)
            or old_sample != sample or not isinstance(history, list) or not history):
        raise ValueError("FuelCast VQR restart checkpoint does not match the saved run")
    valid = []
    for entry in history:
        weights = np.asarray(entry.get("weights"), dtype=np.float64)
        loss = entry.get("objective_scaled_mse")
        if weights.shape != (12,) or not np.isfinite(weights).all() or not np.isfinite(loss):
            raise ValueError("FuelCast VQR restart checkpoint has invalid optimizer history")
        valid.append((float(loss), int(entry["evaluation"]), weights))
    best = min(valid, key=lambda item: (item[0], item[1]))
    return best[2], previous["attempt_id"]


def _predict_validation(vqr, split: SavedVQRValidation, target_scaler) -> tuple[np.ndarray, float]:
    start = time.perf_counter()
    x = split.validation.features.to_numpy(dtype=np.float64)
    results = []
    for offset in range(0, len(x), VQR_BATCH_SIZE):
        if time.perf_counter() - start > VQR_VALIDATION_WALL_SECONDS:
            raise TimeoutError("FuelCast VQR validation exceeded its 3600-second elapsed-time budget")
        scaled = np.asarray(vqr.predict(x[offset:offset + VQR_BATCH_SIZE]), dtype=np.float64).reshape(-1)
        if (len(scaled) != min(VQR_BATCH_SIZE, len(x) - offset)
                or not np.isfinite(scaled).all() or np.any(np.abs(scaled) > 1 + 1e-8)):
            raise ValueError("FuelCast VQR returned invalid validation expectations")
        results.append(np.clip(scaled, -1, 1))
    if time.perf_counter() - start > VQR_VALIDATION_WALL_SECONDS:
        raise TimeoutError("FuelCast VQR validation exceeded its 3600-second elapsed-time budget")
    all_scaled = np.concatenate(results)
    predictions = target_scaler.inverse_transform(all_scaled.reshape(-1, 1)).reshape(-1)
    if predictions.shape != split.validation.target.shape or not np.isfinite(predictions).all():
        raise ValueError("FuelCast VQR returned invalid kg/s validation predictions")
    return predictions, time.perf_counter() - start


def verify_candidate(run_dir: Path, candidate_dir: Path) -> dict:
    """Fresh-process integrity and one-row reconstruction check; no retraining."""
    candidate_dir = Path(candidate_dir)
    manifest = json.loads((candidate_dir / "candidate_manifest.json").read_text(encoding="utf-8"))
    split = load_saved_vqr_validation(
        run_dir, manifest["dataset_version"], manifest["canonical_sha256"],
    )
    loaded = load_vqr_candidate(candidate_dir, split)
    with np.load(candidate_dir / "validation_predictions.npz", allow_pickle=False) as stored:
        if set(stored.files) != {"record_id", "vessel_id", "time_index", "prediction"}:
            raise ValueError("FuelCast VQR validation prediction schema mismatch")
        if (stored["record_id"].tolist() != split.validation.record_id.tolist()
                or stored["vessel_id"].tolist() != split.validation.vessel_id.tolist()
                or not np.array_equal(stored["time_index"], split.validation.time_index)):
            raise ValueError("FuelCast VQR validation prediction identities mismatch")
        saved_first = float(stored["prediction"][0])
    actual_first = float(loaded.predict_angles(split.validation.features.iloc[[0]])[0])
    if not np.isclose(actual_first, saved_first, rtol=1e-8, atol=1e-9):
        raise ValueError("FuelCast VQR fresh-process prediction differs")
    return manifest


def train_vqr(config: FuelCastVQRConfig) -> FuelCastVQRArtifact:
    split = load_saved_vqr_validation(
        config.run_dir, config.expected_version, config.expected_canonical_sha256,
    )
    _, target_scaler = _validate_saved_scalers(split)
    (_, _, _, _, VQR, _, COBYLA, QMLEstimator) = quantum_dependencies()
    mode_settings = VQR_MODES[config.mode]
    selected, sample = sample_training(split, mode_settings["training_rows"], config.seed)
    root = split.run_dir / "06_quantum" / "vqr"
    root.mkdir(parents=True, exist_ok=True)
    published = root / config.mode
    if os.path.lexists(published):
        raise FileExistsError(f"FuelCast VQR mode already published: {published}")
    staging = Path(tempfile.mkdtemp(prefix=f".{config.mode}-staging-", dir=root))
    candidate = staging / "candidate"
    candidate.mkdir()
    history_path = candidate / "optimizer_history.json"
    feature_map, ansatz, observable = build_vqr_circuits()
    default_initial = np.random.default_rng(config.seed).uniform(-0.1, 0.1, size=ansatz.num_parameters)
    initial, resumed_from = _restart_point(
        config.resume_checkpoint, split, sample, config.mode, config.seed,
        default_initial,
    )
    attempt_id = uuid.uuid4().hex
    attempt = {
        "attempt_id": attempt_id, "resumed_from_attempt_id": resumed_from,
        "restart_semantics": "new_COBYLA_run_from_previous_best_loss" if resumed_from else "new_COBYLA_run",
        "run_id": split.run_dir.name, "dataset_version": split.dataset_version,
        "canonical_sha256": split.canonical_sha256,
        "feature_schema_sha256": split.schema_sha256,
        "split_manifest_sha256": split.split_manifest_sha256,
        "sample_record_ids_sha256": _sample_digest(sample),
        "mode": config.mode, "seed": config.seed,
        "initial_point": initial.tolist(),
    }
    _write_json_atomic(candidate / "attempt_manifest.json", attempt)
    _write_json_atomic(candidate / "sample_manifest.json", sample)
    history: list[dict] = []
    fit_start = time.perf_counter()
    _write_json_atomic(history_path, history)

    def callback(weights, objective):
        elapsed = time.perf_counter() - fit_start
        values = np.asarray(weights, dtype=np.float64)
        if values.shape != (12,) or not np.isfinite(values).all() or not np.isfinite(objective):
            raise ValueError("FuelCast VQR optimizer returned invalid state")
        history.append({"evaluation": len(history) + 1, "objective_scaled_mse": float(objective),
                        "elapsed_seconds": elapsed, "weights": values.tolist()})
        _write_json_atomic(history_path, history)
        if len(history) > mode_settings["maxiter"]:
            raise ValueError("FuelCast VQR optimizer exceeded the configured evaluation budget")
        if elapsed > mode_settings["fit_wall_seconds"]:
            raise TimeoutError(f"FuelCast VQR fit exceeded its {mode_settings['fit_wall_seconds']}-second elapsed-time budget")

    vqr = VQR(
        feature_map=feature_map, ansatz=ansatz, observable=observable,
        estimator=QMLEstimator(default_precision=0.0),
        optimizer=COBYLA(maxiter=mode_settings["maxiter"]),
        loss="squared_error", initial_point=initial, callback=callback,
    )
    vqr.fit(split.train.features.iloc[selected].to_numpy(dtype=np.float64),
            split.train.scaled_target[selected])
    fit_seconds = time.perf_counter() - fit_start
    if fit_seconds > mode_settings["fit_wall_seconds"]:
        raise TimeoutError(f"FuelCast VQR fit exceeded its {mode_settings['fit_wall_seconds']}-second elapsed-time budget")
    weights = np.asarray(vqr.weights, dtype=np.float64)
    if weights.shape != (12,) or not np.isfinite(weights).all():
        raise ValueError("FuelCast VQR learned invalid weights")
    predictions, predict_seconds = _predict_validation(vqr, split, target_scaler)
    overall = _metrics(split.validation.target, predictions)
    by_vessel = {}
    for vessel in EXPECTED_CONFIGS:
        mask = split.validation.vessel_id == vessel
        by_vessel[vessel] = {"rows": int(mask.sum()),
                             **_metrics(split.validation.target[mask], predictions[mask])}
    _write_json_atomic(candidate / "circuit_config.json", circuit_configuration())
    np.savez_compressed(candidate / "weights.npz", weights=weights)
    shutil.copyfile(split.preprocessor_path, candidate / "vqr_preprocessor.pkl")
    shutil.copyfile(split.target_scaler_path, candidate / "vqr_target_scaler.pkl")
    shutil.copyfile(split.feature_schema_path, candidate / "feature_schema.json")
    np.savez_compressed(
        candidate / "validation_predictions.npz",
        record_id=split.validation.record_id, vessel_id=split.validation.vessel_id,
        time_index=split.validation.time_index, prediction=predictions,
    )
    metrics = {"selection_scope": "vqr_validation_only", "mode": config.mode,
               "benchmark_eligible": config.mode == "normal", "validation_rows": len(predictions),
               "validation_metrics": overall, "validation_per_vessel": by_vessel,
               "prediction_seconds": predict_seconds}
    _write_json_atomic(candidate / "validation_metrics.json", metrics)
    names = ("circuit_config.json", "weights.npz", "vqr_preprocessor.pkl",
             "vqr_target_scaler.pkl", "feature_schema.json", "sample_manifest.json",
             "optimizer_history.json", "attempt_manifest.json",
             "validation_predictions.npz", "validation_metrics.json")
    manifest = {
        "candidate": "vqr", "model_family": "quantum", "algorithm": "VQR",
        "backend": "simulator", "real_quantum_hardware": False,
        "selection_scope": "vqr_validation_only", "benchmark_eligible": config.mode == "normal",
        "dataset_id": DATASET_ID, "dataset_version": split.dataset_version,
        "canonical_sha256": split.canonical_sha256, "run_id": split.run_dir.name,
        "feature_order": list(VQR_FEATURES), "feature_schema_sha256": split.schema_sha256,
        "split_manifest_sha256": split.split_manifest_sha256,
        "phase4_artifact_sha256": split.source_hashes,
        "target": VQR_TARGET, "target_unit": "kg/s", "mode": config.mode,
        "seed": config.seed, "training_rows_full": len(split.train.target),
        "training_rows_sampled": len(selected), "validation_rows": len(predictions),
        "partition_counts": split.partition_counts, "optimizer": "COBYLA",
        "optimizer_maxiter": mode_settings["maxiter"], "fit_loss": "scaled_target_squared_error",
        "fit_wall_seconds": mode_settings["fit_wall_seconds"],
        "validation_wall_seconds": VQR_VALIDATION_WALL_SECONDS,
        "optimizer_evaluations": len(history), "fit_seconds": fit_seconds,
        "attempt_id": attempt_id, "resumed_from_attempt_id": resumed_from,
        "initial_point": initial.tolist(),
        "prediction_seconds": predict_seconds, "validation_metrics": overall,
        "validation_per_vessel": by_vessel, "dependency_versions": dependency_versions(),
        "artifact_sha256": {name: sha256_file(candidate / name) for name in names},
    }
    _write_json_atomic(candidate / "candidate_manifest.json", manifest)
    subprocess.run(
        [sys.executable, "-m", "greenfleet.ml_pipeline.quantum.fuelcast_vqr", "verify",
         "--run-dir", str(split.run_dir), "--candidate-dir", str(candidate)],
        check=True, stdout=subprocess.DEVNULL,
    )
    os.replace(staging, published)
    final = published / "candidate"
    return FuelCastVQRArtifact(
        final, final / "candidate_manifest.json", final / "weights.npz",
        final / "validation_metrics.json", final / "validation_predictions.npz",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Train or verify simulator FuelCast VQR")
    commands = parser.add_subparsers(dest="command", required=True)
    train = commands.add_parser("train", help="fit on saved training rows and score validation")
    train.add_argument("--run-dir", type=Path, required=True)
    train.add_argument("--mode", choices=tuple(VQR_MODES), required=True)
    train.add_argument("--expected-version", required=True)
    train.add_argument("--expected-canonical-sha256", required=True)
    train.add_argument("--resume-checkpoint", type=Path,
                       help="absolute candidate directory from a previous unpublished attempt")
    verify = commands.add_parser("verify", help="verify artifact and one-row reconstruction")
    verify.add_argument("--run-dir", type=Path, required=True)
    verify.add_argument("--candidate-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "train":
        config = FuelCastVQRConfig(args.run_dir, args.mode, args.expected_version,
                                   args.expected_canonical_sha256,
                                   resume_checkpoint=args.resume_checkpoint)
        artifact = train_vqr(config)
        print(f"FuelCast VQR {args.mode}: {artifact.candidate_dir}")
    else:
        result = verify_candidate(args.run_dir, args.candidate_dir)
        print(f"Verified FuelCast VQR {result['mode']}: {args.candidate_dir}")


if __name__ == "__main__":
    from greenfleet.ml_pipeline.quantum.fuelcast_vqr import main as package_main
    package_main()
