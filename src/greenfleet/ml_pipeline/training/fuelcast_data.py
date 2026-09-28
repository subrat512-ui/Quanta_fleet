"""Read the immutable Phase 4 training and validation partitions only."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from greenfleet.constants.fuelcast import (
    CANONICAL_FEATURES, CANONICAL_TARGET, DATASET_ID, EXPECTED_CONFIGS,
)
from greenfleet.constants.fuelcast_classical import CLASSICAL_FEATURES


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True)
class Partition:
    features: pd.DataFrame
    target: np.ndarray
    record_id: np.ndarray
    vessel_id: np.ndarray
    time_index: np.ndarray


@dataclass(frozen=True)
class SavedValidationSplit:
    train: Partition
    validation: Partition
    run_dir: Path
    dataset_version: str
    canonical_sha256: str
    schema_sha256: str
    split_manifest_sha256: str
    source_hashes: dict[str, str]
    partition_counts: dict[str, int]


def _load_partition(stage: Path, name: str, manifest: dict) -> Partition:
    filename = f"{name}.npz"
    expected_hash = manifest.get("artifact_sha256", {}).get(filename)
    if not expected_hash or sha256_file(stage / filename) != expected_hash:
        raise ValueError(f"FuelCast {filename} hash mismatch")
    with np.load(stage / filename, allow_pickle=False) as source:
        required = {"features", "vqr_features", "target", "vqr_target", "record_id", "vessel_id", "time_index"}
        if set(source.files) != required:
            raise ValueError(f"FuelCast {name} array keys mismatch")
        x = np.asarray(source["features"], dtype=np.float64)
        y = np.asarray(source["target"], dtype=np.float64)
        ids = np.asarray(source["record_id"])
        vessels = np.asarray(source["vessel_id"])
        times = np.asarray(source["time_index"])
    n = manifest.get("partition_counts", {}).get(name)
    if (not isinstance(n, int) or n <= 0 or x.shape != (n, len(CLASSICAL_FEATURES))
            or any(value.shape != (n,) for value in (y, ids, vessels, times))):
        raise ValueError(f"FuelCast {name} array shape/count mismatch")
    if not np.isfinite(x).all() or not np.isfinite(y).all() or (y < 0).any():
        raise ValueError(f"FuelCast {name} features or target are invalid")
    if not np.issubdtype(times.dtype, np.integer):
        raise ValueError(f"FuelCast {name} time indexes must be integer")
    expected_ids = []
    cursor = 0
    for vessel in EXPECTED_CONFIGS:
        detail = manifest.get("per_vessel", {}).get(vessel, {}).get(name)
        if not isinstance(detail, dict) or not isinstance(detail.get("count"), int) or detail["count"] <= 0:
            raise ValueError(f"FuelCast {name} manifest lacks {vessel}")
        count = detail["count"]
        selected = slice(cursor, cursor + count)
        vessel_times = times[selected]
        if (len(vessel_times) != count or not np.all(vessels[selected] == vessel)
                or int(vessel_times[0]) != detail.get("first_time_index")
                or int(vessel_times[-1]) != detail.get("last_time_index")
                or np.any(np.diff(vessel_times) <= 0)):
            raise ValueError(f"FuelCast {name} vessel/time order mismatch")
        expected_ids.extend(detail.get("record_ids", []))
        cursor += count
    if cursor != n or ids.tolist() != expected_ids or len(set(expected_ids)) != n:
        raise ValueError(f"FuelCast {name} row identities mismatch")
    return Partition(pd.DataFrame(x, columns=CLASSICAL_FEATURES), y, ids, vessels, times)


def load_saved_validation(
    run_dir: Path, expected_version: str, expected_canonical_sha256: str,
) -> SavedValidationSplit:
    """Validate source identity, then load only train.npz and validation.npz."""
    run_dir = Path(run_dir)
    if not run_dir.is_absolute():
        raise ValueError("FuelCast run directory must be explicit and absolute")
    run_dir = run_dir.resolve(strict=True)
    stage = run_dir / "04_transformation"
    manifest_path = stage / "split_manifest.json"
    schema_path = stage / "feature_schema.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    schema_hash = sha256_file(schema_path)
    audit_path = run_dir / "02_etl" / "etl_audit.json"
    canonical_path = run_dir / "02_etl" / "fuelcast_clean.csv"
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    if (manifest.get("dataset_id") != DATASET_ID or schema.get("dataset_id") != DATASET_ID
            or manifest.get("source_run_id") != run_dir.name
            or audit.get("source_run_id") != run_dir.name
            or any(item.get("dataset_version") != expected_version for item in (manifest, schema, audit))
            or manifest.get("canonical_sha256") != expected_canonical_sha256
            or audit.get("canonical_sha256") != expected_canonical_sha256
            or sha256_file(canonical_path) != expected_canonical_sha256
            or manifest.get("etl_audit_sha256") != sha256_file(audit_path)):
        raise ValueError("FuelCast run/version/canonical provenance mismatch")
    partition_counts = manifest.get("partition_counts", {})
    if (set(partition_counts) != {"train", "validation", "test"}
            or any(not isinstance(count, int) or count <= 0 for count in partition_counts.values())
            or audit.get("totals", {}).get("output_rows") != sum(partition_counts.values())):
        raise ValueError("FuelCast partition counts do not match ETL audit")
    for vessel in EXPECTED_CONFIGS:
        details = manifest.get("per_vessel", {}).get(vessel, {})
        if (set(details) != {"train", "validation", "test"}
                or any(not isinstance(details[name].get("count"), int) or details[name]["count"] <= 0
                       for name in ("train", "validation", "test"))
                or audit.get("per_vessel", {}).get(vessel, {}).get("output_rows")
                   != sum(details[name]["count"] for name in ("train", "validation", "test"))):
            raise ValueError(f"FuelCast {vessel} partition counts do not match ETL audit")
    for name in ("train", "validation", "test"):
        if sum(manifest["per_vessel"][vessel][name]["count"] for vessel in EXPECTED_CONFIGS) != partition_counts[name]:
            raise ValueError(f"FuelCast {name} partition count mismatch")
    hashes = manifest.get("artifact_sha256", {})
    if hashes.get("feature_schema.json") != schema_hash:
        raise ValueError("FuelCast feature schema hash mismatch")
    if hashes.get("preprocessor.pkl") != sha256_file(stage / "preprocessor.pkl"):
        raise ValueError("FuelCast classical preprocessor hash mismatch")
    if (schema.get("raw_features") != list(CANONICAL_FEATURES)
            or schema.get("classical_features") != list(CLASSICAL_FEATURES)
            or schema.get("target") != CANONICAL_TARGET
            or schema.get("units", {}).get(CANONICAL_TARGET) != "kg/s"
            or schema.get("array_keys") != ["features", "vqr_features", "target", "vqr_target", "record_id", "vessel_id", "time_index"]
            or manifest.get("split_strategy") != "per_vessel_chronological_70_15_15"):
        raise ValueError("FuelCast feature or split contract mismatch")
    train = _load_partition(stage, "train", manifest)
    validation = _load_partition(stage, "validation", manifest)
    if set(train.record_id.tolist()) & set(validation.record_id.tolist()):
        raise ValueError("FuelCast training/validation identities overlap")
    for vessel in EXPECTED_CONFIGS:
        train_last = manifest["per_vessel"][vessel]["train"]["last_time_index"]
        validation_first = manifest["per_vessel"][vessel]["validation"]["first_time_index"]
        if train_last >= validation_first:
            raise ValueError(f"FuelCast {vessel} training/validation chronology overlaps")
    return SavedValidationSplit(
        train, validation, run_dir, expected_version, expected_canonical_sha256,
        schema_hash, sha256_file(manifest_path),
        {name: hashes[name] for name in ("train.npz", "validation.npz", "preprocessor.pkl")},
        {name: manifest["partition_counts"][name] for name in ("train", "validation")},
    )
