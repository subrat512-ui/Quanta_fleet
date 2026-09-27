"""Validate a pinned FuelCast snapshot and publish its canonical ETL output."""

import argparse
import csv
import hashlib
import io
import json
import math
import os
import re
import shutil
import tempfile
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path

from greenfleet.artifacts.fuelcast_etl_artifact import FuelCastETLArtifact
from greenfleet.constants.fuelcast import (
    CANONICAL_COLUMNS, CANONICAL_FEATURES, CANONICAL_TARGET, CANONICAL_UNITS,
    DATASET_ID, EXPECTED_CONFIGS, RAW_COLUMNS, SOURCE_LICENSE,
    SOURCE_MODEL_COLUMNS, SOURCE_SPLIT, SOURCE_TO_CANONICAL,
)
from greenfleet.constants.training_pipeline_constants import ARTIFACTS_DIR


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fingerprint(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _record_id(revision: str, vessel: str, time_index: int) -> str:
    """SHA-256 of three UTF-8 fields, each prefixed by its 8-byte length."""
    digest = hashlib.sha256()
    for value in (revision, vessel, str(time_index)):
        encoded = value.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def _validated_manifest(manifest: dict) -> tuple[str, dict[str, int]]:
    if manifest.get("dataset_id") != DATASET_ID:
        raise ValueError("FuelCast source manifest dataset_id mismatch")
    revision = manifest.get("dataset_version")
    if not isinstance(revision, str) or re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        raise ValueError("FuelCast source manifest has invalid dataset_version")
    if manifest.get("license") != SOURCE_LICENSE or manifest.get("split") != SOURCE_SPLIT:
        raise ValueError("FuelCast source manifest license or split mismatch")
    if manifest.get("loaded_configurations") != list(EXPECTED_CONFIGS):
        raise ValueError("FuelCast source manifest configuration mismatch")
    if manifest.get("raw_columns") != list(RAW_COLUMNS):
        raise ValueError("FuelCast source manifest raw column mismatch")
    counts = manifest.get("row_counts")
    if not isinstance(counts, dict) or set(counts) != set(EXPECTED_CONFIGS):
        raise ValueError("FuelCast source manifest row_counts mismatch")
    if any(type(counts[name]) is not int or counts[name] <= 0 for name in EXPECTED_CONFIGS):
        raise ValueError("FuelCast source manifest has invalid vessel row count")
    if manifest.get("total_rows") != sum(counts.values()):
        raise ValueError("FuelCast source manifest total_rows mismatch")
    schemas = manifest.get("source_schemas")
    fingerprints = manifest.get("schema_fingerprints")
    if not isinstance(schemas, dict) or not isinstance(fingerprints, dict):
        raise ValueError("FuelCast source manifest missing schema metadata")
    if set(schemas) != set(EXPECTED_CONFIGS) or set(fingerprints) != set(EXPECTED_CONFIGS):
        raise ValueError("FuelCast source manifest schema vessel mismatch")
    for vessel in EXPECTED_CONFIGS:
        pairs = schemas[vessel]
        if not isinstance(pairs, list) or any(
            not isinstance(pair, list) or len(pair) != 2 or
            not all(isinstance(item, str) for item in pair) for pair in pairs
        ):
            raise ValueError(f"FuelCast {vessel} malformed source schema")
        names = [pair[0] for pair in pairs]
        if len(names) != len(set(names)) or not set(SOURCE_MODEL_COLUMNS).issubset(names) or "index" not in names:
            raise ValueError(f"FuelCast {vessel} source schema missing required columns")
        if fingerprints[vessel] != _fingerprint(pairs):
            raise ValueError(f"FuelCast {vessel} schema fingerprint mismatch")
    combined = [[name, schemas[name]] for name in EXPECTED_CONFIGS]
    if manifest.get("combined_schema_fingerprint") != _fingerprint(combined):
        raise ValueError("FuelCast combined schema fingerprint mismatch")
    if not isinstance(manifest.get("retrieved_at_utc"), str) or not manifest["retrieved_at_utc"]:
        raise ValueError("FuelCast source manifest missing retrieval timestamp")
    if not isinstance(manifest.get("snapshot_sha256"), str) or re.fullmatch(
        r"[0-9a-f]{64}", manifest["snapshot_sha256"]
    ) is None:
        raise ValueError("FuelCast source manifest missing snapshot hash")
    return revision, counts


def _number(value: str) -> tuple[float | None, str | None]:
    if not value.strip():
        return None, "missing"
    try:
        number = float(value)
    except ValueError:
        return None, "nonnumeric"
    if not math.isfinite(number):
        return None, "nonfinite"
    return number, None


def _time(value: str) -> tuple[int | None, str | None]:
    if not value.strip():
        return None, "missing"
    try:
        number = Decimal(value)
    except InvalidOperation:
        return None, "nonnumeric"
    if not number.is_finite():
        return None, "nonfinite"
    if number < 0:
        return None, "negative"
    if number != number.to_integral_value():
        return None, "nonintegral"
    return int(number), None


def _out_of_range(feature: str, value: float) -> bool:
    if feature == "wind_direction":
        return value < 0 or value > 360
    if feature == "wave_period":
        return value <= 0
    return value < 0


def run_fuelcast_etl(run_dir: Path) -> FuelCastETLArtifact:
    """Read Phase 1 inputs and atomically publish an immutable 02_etl stage."""
    run_dir = Path(run_dir)
    source_dir = run_dir / "01_source"
    snapshot_path = source_dir / "fuelcast_raw.csv"
    manifest_path = source_dir / "source_manifest.json"
    output_dir = run_dir / "02_etl"
    if os.path.lexists(output_dir):
        raise FileExistsError(f"FuelCast ETL stage already exists: {output_dir}")
    if not snapshot_path.is_file() or not manifest_path.is_file():
        raise FileNotFoundError("FuelCast source snapshot and manifest are required")
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    revision, expected_counts = _validated_manifest(manifest)
    snapshot_bytes = snapshot_path.read_bytes()
    snapshot_hash = hashlib.sha256(snapshot_bytes).hexdigest()
    if snapshot_hash != manifest["snapshot_sha256"]:
        raise ValueError("FuelCast snapshot SHA-256 mismatch")

    raw_rows = {name: [] for name in EXPECTED_CONFIGS}
    with io.StringIO(snapshot_bytes.decode("utf-8"), newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != list(RAW_COLUMNS):
            raise ValueError("FuelCast snapshot column order mismatch")
        for row in reader:
            vessel = row["vessel_id"]
            if vessel not in raw_rows:
                raise ValueError(f"Unexpected FuelCast vessel_id: {vessel!r}")
            if None in row or any(value is None for value in row.values()):
                raise ValueError("FuelCast snapshot has malformed CSV row")
            raw_rows[vessel].append(row)
    actual_counts = {name: len(raw_rows[name]) for name in EXPECTED_CONFIGS}
    if actual_counts != expected_counts:
        raise ValueError(f"FuelCast source row count mismatch: {actual_counts}")

    cleaned = []
    vessel_audits = {}
    output_counts = {}
    for vessel in EXPECTED_CONFIGS:
        rows = raw_rows[vessel]
        seen_raw = set()
        drops = {"exact_duplicates": 0, "invalid_target": Counter(), "invalid_time": Counter()}
        feature_coercions = {name: Counter() for name in CANONICAL_FEATURES}
        range_violations = Counter()
        feature_nulls = Counter()
        seen_keys = set()
        output_count = 0
        for row in rows:
            raw_key = tuple(row[name] for name in RAW_COLUMNS)
            if raw_key in seen_raw:
                drops["exact_duplicates"] += 1
                continue
            seen_raw.add(raw_key)
            target, target_error = _number(row[SOURCE_MODEL_COLUMNS[-1]])
            if target_error:
                drops["invalid_target"][target_error] += 1
                continue
            if target < 0:
                drops["invalid_target"]["negative"] += 1
                continue
            time_index, time_error = _time(row["time_index"])
            if time_error:
                drops["invalid_time"][time_error] += 1
                continue
            key = (vessel, time_index)
            if key in seen_keys:
                raise ValueError(f"Conflicting FuelCast vessel/time key: {key}")
            seen_keys.add(key)
            canonical = {
                "record_id": _record_id(revision, vessel, time_index),
                "dataset_version": revision,
                "vessel_id": vessel,
                "time_index": time_index,
                CANONICAL_TARGET: target,
            }
            for raw_name in SOURCE_MODEL_COLUMNS[:-1]:
                feature = SOURCE_TO_CANONICAL[raw_name]
                value, error = _number(row[raw_name])
                if error:
                    feature_coercions[feature][error] += 1
                elif _out_of_range(feature, value):
                    range_violations[feature] += 1
                    value = None
                if value is None:
                    feature_nulls[feature] += 1
                canonical[feature] = value
            cleaned.append(canonical)
            output_count += 1
        removed = drops["exact_duplicates"] + sum(drops["invalid_target"].values()) + sum(drops["invalid_time"].values())
        if len(rows) != removed + output_count:
            raise AssertionError("FuelCast ETL audit counts do not reconcile")
        if output_count == 0:
            raise ValueError(f"FuelCast {vessel} has no valid canonical rows")
        output_counts[vessel] = output_count
        vessel_audits[vessel] = {
            "input_rows": len(rows), "output_rows": output_count,
            "exact_duplicates_removed": drops["exact_duplicates"],
            "invalid_targets_removed": dict(drops["invalid_target"]),
            "invalid_times_removed": dict(drops["invalid_time"]),
            "feature_coercions": {name: dict(count) for name, count in feature_coercions.items()},
            "feature_range_violations": dict(range_violations),
            "remaining_feature_nulls": dict(feature_nulls),
        }
    cleaned.sort(key=lambda row: (row["vessel_id"], row["time_index"]))

    stage = Path(tempfile.mkdtemp(prefix=".02_etl-data-", dir=run_dir))
    try:
        canonical_path = stage / "fuelcast_clean.csv"
        with canonical_path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=CANONICAL_COLUMNS)
            writer.writeheader()
            writer.writerows(cleaned)
        audit = {
            "source_run_id": run_dir.name,
            "source_manifest_path": str(manifest_path),
            "source_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
            "dataset_id": DATASET_ID,
            "dataset_version": revision,
            "retrieved_at_utc": manifest["retrieved_at_utc"],
            "source_snapshot_sha256": snapshot_hash,
            "canonical_sha256": _sha256(canonical_path),
            "source_to_canonical": SOURCE_TO_CANONICAL,
            "canonical_columns": list(CANONICAL_COLUMNS),
            "units": CANONICAL_UNITS,
            "record_id_encoding": "SHA-256 of UTF-8 revision, vessel_id, integer time_index; each field prefixed with an unsigned 8-byte big-endian length",
            "per_vessel": vessel_audits,
            "totals": {
                "input_rows": sum(expected_counts.values()),
                "output_rows": sum(output_counts.values()),
                "exact_duplicates_removed": sum(a["exact_duplicates_removed"] for a in vessel_audits.values()),
                "invalid_targets_removed": sum(sum(a["invalid_targets_removed"].values()) for a in vessel_audits.values()),
                "invalid_times_removed": sum(sum(a["invalid_times_removed"].values()) for a in vessel_audits.values()),
                "feature_coercions": {
                    name: dict(sum((Counter(a["feature_coercions"][name]) for a in vessel_audits.values()), Counter()))
                    for name in CANONICAL_FEATURES
                },
                "feature_range_violations": dict(sum((Counter(a["feature_range_violations"]) for a in vessel_audits.values()), Counter())),
                "remaining_feature_nulls": dict(sum((Counter(a["remaining_feature_nulls"]) for a in vessel_audits.values()), Counter())),
            },
        }
        (stage / "etl_audit.json").write_text(json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        # The relative symlink is created atomically and refuses any existing
        # destination, including an empty directory or a broken symlink.
        os.symlink(stage.name, output_dir, target_is_directory=True)
    except BaseException:
        shutil.rmtree(stage)
        raise
    return FuelCastETLArtifact(output_dir / "fuelcast_clean.csv", output_dir / "etl_audit.json", revision, output_counts)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and canonicalize a FuelCast source run")
    parser.add_argument("--run-id", required=True, help="Existing artifacts run directory name")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", args.run_id) or args.run_id in {".", ".."}:
        parser.error("--run-id must be a single safe directory name")
    artifact = run_fuelcast_etl(ARTIFACTS_DIR / args.run_id)
    print(f"FuelCast canonical dataset: {artifact.canonical_path}")
    print(f"ETL audit: {artifact.audit_path}")
    print(f"Rows: {artifact.row_counts} (total {artifact.total_rows})")


if __name__ == "__main__":
    main()
