"""Read only the saved Phase 4 training and validation VQR contract."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from greenfleet.constants.fuelcast import DATASET_ID, EXPECTED_CONFIGS
from greenfleet.constants.fuelcast_vqr import VQR_FEATURES, VQR_TARGET
from greenfleet.ml_pipeline.training.fuelcast_data import sha256_file


@dataclass(frozen=True)
class VQRPartition:
    features: pd.DataFrame
    target: np.ndarray
    scaled_target: np.ndarray
    record_id: np.ndarray
    vessel_id: np.ndarray
    time_index: np.ndarray


@dataclass(frozen=True)
class SavedVQRValidation:
    train: VQRPartition
    validation: VQRPartition
    run_dir: Path
    dataset_version: str
    canonical_sha256: str
    schema_sha256: str
    split_manifest_sha256: str
    source_hashes: dict[str, str]
    partition_counts: dict[str, int]
    preprocessor_path: Path
    target_scaler_path: Path
    feature_schema_path: Path


def _load_partition(stage: Path, name: str, manifest: dict) -> VQRPartition:
    filename = f"{name}.npz"
    expected_hash = manifest.get("artifact_sha256", {}).get(filename)
    if not expected_hash or sha256_file(stage / filename) != expected_hash:
        raise ValueError(f"FuelCast VQR {filename} hash mismatch")
    with np.load(stage / filename, allow_pickle=False) as content:
        required = {"features", "vqr_features", "target", "vqr_target",
                    "record_id", "vessel_id", "time_index"}
        if set(content.files) != required:
            raise ValueError(f"FuelCast VQR {name} array keys mismatch")
        angles = np.asarray(content["vqr_features"], dtype=np.float64)
        target = np.asarray(content["target"], dtype=np.float64)
        scaled = np.asarray(content["vqr_target"], dtype=np.float64)
        ids = np.asarray(content["record_id"])
        vessels = np.asarray(content["vessel_id"])
        times = np.asarray(content["time_index"])
    n = manifest.get("partition_counts", {}).get(name)
    if (not isinstance(n, int) or n <= 0 or angles.shape != (n, len(VQR_FEATURES))
            or any(a.shape != (n,) for a in (target, scaled, ids, vessels, times))):
        raise ValueError(f"FuelCast VQR {name} array shape/count mismatch")
    if (not np.isfinite(angles).all() or not np.isfinite(target).all()
            or not np.isfinite(scaled).all() or (target < 0).any()
            or np.any(angles[:, (0, 1, 3, 4, 5)] < -1e-12)
            or np.any(angles[:, (0, 1, 3, 4, 5)] > np.pi + 1e-12)
            or np.any(angles[:, 2] < -1e-12)
            or np.any(angles[:, 2] > 2 * np.pi + 1e-12)):
        raise ValueError(f"FuelCast VQR {name} features or target are invalid")
    if not np.issubdtype(times.dtype, np.integer):
        raise ValueError(f"FuelCast VQR {name} time indexes must be integer")
    expected_ids: list[str] = []
    cursor = 0
    for vessel in EXPECTED_CONFIGS:
        detail = manifest.get("per_vessel", {}).get(vessel, {}).get(name)
        if not isinstance(detail, dict) or not isinstance(detail.get("count"), int) or detail["count"] <= 0:
            raise ValueError(f"FuelCast VQR {name} manifest lacks {vessel}")
        count = detail["count"]
        selected = slice(cursor, cursor + count)
        vessel_times = times[selected]
        if (len(vessel_times) != count or not np.all(vessels[selected] == vessel)
                or int(vessel_times[0]) != detail.get("first_time_index")
                or int(vessel_times[-1]) != detail.get("last_time_index")
                or np.any(np.diff(vessel_times) <= 0)):
            raise ValueError(f"FuelCast VQR {name} vessel/time order mismatch")
        expected_ids.extend(detail.get("record_ids", []))
        cursor += count
    if cursor != n or ids.tolist() != expected_ids or len(set(expected_ids)) != n:
        raise ValueError(f"FuelCast VQR {name} row identities mismatch")
    return VQRPartition(pd.DataFrame(angles, columns=VQR_FEATURES), target,
                        scaled, ids, vessels, times)


def load_saved_vqr_validation(
    run_dir: Path, expected_version: str, expected_canonical_sha256: str,
) -> SavedVQRValidation:
    """Validate provenance and load only train.npz and validation.npz."""
    run_dir = Path(run_dir)
    if not run_dir.is_absolute():
        raise ValueError("FuelCast run directory must be explicit and absolute")
    run_dir = run_dir.resolve(strict=True)
    stage = run_dir / "04_transformation"
    manifest_path = stage / "split_manifest.json"
    schema_path = stage / "feature_schema.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    audit_path = run_dir / "02_etl" / "etl_audit.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    if (manifest.get("dataset_id") != DATASET_ID or schema.get("dataset_id") != DATASET_ID
            or manifest.get("source_run_id") != run_dir.name
            or audit.get("source_run_id") != run_dir.name
            or any(x.get("dataset_version") != expected_version for x in (manifest, schema, audit))
            or manifest.get("canonical_sha256") != expected_canonical_sha256
            or audit.get("canonical_sha256") != expected_canonical_sha256
            or manifest.get("etl_audit_sha256") != sha256_file(audit_path)):
        raise ValueError("FuelCast VQR run/version/canonical provenance mismatch")
    counts = manifest.get("partition_counts", {})
    if (set(counts) != {"train", "validation", "test"}
            or any(not isinstance(count, int) or count <= 0 for count in counts.values())
            or audit.get("totals", {}).get("output_rows") != sum(counts.values())):
        raise ValueError("FuelCast VQR partition counts do not match ETL audit")
    for vessel in EXPECTED_CONFIGS:
        details = manifest.get("per_vessel", {}).get(vessel, {})
        if (set(details) != {"train", "validation", "test"}
                or any(not isinstance(details[name].get("count"), int)
                       or details[name]["count"] <= 0 for name in counts)
                or audit.get("per_vessel", {}).get(vessel, {}).get("output_rows")
                   != sum(details[name]["count"] for name in counts)):
            raise ValueError(f"FuelCast VQR {vessel} counts do not match ETL audit")
    for name in counts:
        if sum(manifest["per_vessel"][vessel][name]["count"]
               for vessel in EXPECTED_CONFIGS) != counts[name]:
            raise ValueError(f"FuelCast VQR {name} partition count mismatch")
    hashes = manifest.get("artifact_sha256", {})
    required_hashes = ("feature_schema.json", "train.npz", "validation.npz",
                       "vqr_preprocessor.pkl", "vqr_target_scaler.pkl")
    for name in required_hashes:
        if hashes.get(name) != sha256_file(stage / name):
            raise ValueError(f"FuelCast VQR {name} hash mismatch")
    if (schema.get("raw_features") != list(VQR_FEATURES)
            or schema.get("vqr_features") != list(VQR_FEATURES)
            or schema.get("target") != VQR_TARGET
            or schema.get("units", {}).get(VQR_TARGET) != "kg/s"
            or schema.get("array_keys") != ["features", "vqr_features", "target",
                                             "vqr_target", "record_id", "vessel_id", "time_index"]
            or manifest.get("split_strategy") != "per_vessel_chronological_70_15_15"):
        raise ValueError("FuelCast VQR feature or split contract mismatch")
    train = _load_partition(stage, "train", manifest)
    validation = _load_partition(stage, "validation", manifest)
    if set(train.record_id.tolist()) & set(validation.record_id.tolist()):
        raise ValueError("FuelCast VQR training/validation identities overlap")
    for vessel in EXPECTED_CONFIGS:
        train_last = manifest["per_vessel"][vessel]["train"]["last_time_index"]
        validation_first = manifest["per_vessel"][vessel]["validation"]["first_time_index"]
        if train_last >= validation_first:
            raise ValueError(f"FuelCast VQR {vessel} training/validation chronology overlaps")
    return SavedVQRValidation(
        train, validation, run_dir, expected_version, expected_canonical_sha256,
        hashes["feature_schema.json"], sha256_file(manifest_path),
        {name: hashes[name] for name in required_hashes},
        {"train": len(train.target), "validation": len(validation.target)},
        stage / "vqr_preprocessor.pkl", stage / "vqr_target_scaler.pkl", schema_path,
    )
