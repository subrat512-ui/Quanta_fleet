"""Pinned, schema-validated FuelCast raw snapshot ingestion."""

import csv
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa
from datasets import get_dataset_config_names, load_dataset
from huggingface_hub import HfApi

from greenfleet.artifacts.fuelcast_source_artifact import FuelCastSourceArtifact
from greenfleet.constants.fuelcast import (
    DATASET_ID,
    EXPECTED_CONFIGS,
    RAW_COLUMNS,
    REQUIRED_SOURCE_COLUMNS,
    SOURCE_LICENSE,
    SOURCE_MODEL_COLUMNS,
    SOURCE_SPLIT,
    SOURCE_TIME_COLUMN,
)

_SHA_PATTERN = re.compile(r"[0-9a-f]{40}")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _schema_fingerprint(schema: object) -> str:
    payload = json.dumps(schema, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _validate_schema(dataset: object, config_name: str) -> tuple[list[list[str]], str]:
    features = dataset.features
    schema = features.arrow_schema
    names = set(schema.names)
    missing = sorted(set(REQUIRED_SOURCE_COLUMNS) - names)
    if missing:
        raise ValueError(f"FuelCast {config_name} missing required columns: {missing}")

    time_type = schema.field(SOURCE_TIME_COLUMN).type
    if not pa.types.is_integer(time_type):
        raise ValueError(
            f"FuelCast {config_name} {SOURCE_TIME_COLUMN} must be integral; got {time_type}"
        )
    for name in SOURCE_MODEL_COLUMNS:
        field_type = schema.field(name).type
        if not (
            pa.types.is_integer(field_type)
            or pa.types.is_floating(field_type)
            or pa.types.is_decimal(field_type)
        ):
            raise ValueError(f"FuelCast {config_name} {name} must be numeric; got {field_type}")

    pairs = [[field.name, str(field.type)] for field in schema]
    return pairs, _schema_fingerprint(pairs)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ingest_fuelcast(run_dir: Path, revision: str | None = None) -> FuelCastSourceArtifact:
    """Publish one pinned raw snapshot and manifest beneath a new run directory.

    The source rows are intentionally left uncleaned for the next ETL phase.
    """
    run_dir = Path(run_dir)
    if run_dir.exists():
        raise FileExistsError(f"FuelCast run directory already exists: {run_dir}")

    info = HfApi().dataset_info(DATASET_ID, revision=revision)
    sha = info.sha
    if not isinstance(sha, str) or _SHA_PATTERN.fullmatch(sha) is None:
        raise RuntimeError(f"FuelCast Hub returned an invalid commit SHA: {sha!r}")

    available = get_dataset_config_names(DATASET_ID, revision=sha)
    missing = sorted(set(EXPECTED_CONFIGS) - set(available))
    if missing:
        raise RuntimeError(f"Missing FuelCast configurations: {missing}")

    run_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{run_dir.name}.source-", dir=run_dir.parent) as staging_name:
        stage = Path(staging_name) / "01_source"
        stage.mkdir()
        snapshot = stage / "fuelcast_raw.csv"
        row_counts: dict[str, int] = {}
        source_schemas: dict[str, list[list[str]]] = {}
        schema_fingerprints: dict[str, str] = {}

        with snapshot.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(RAW_COLUMNS)
            for config_name in EXPECTED_CONFIGS:
                dataset = load_dataset(DATASET_ID, config_name, split=SOURCE_SPLIT, revision=sha)
                schema_pairs, fingerprint = _validate_schema(dataset, config_name)
                source_schemas[config_name] = schema_pairs
                schema_fingerprints[config_name] = fingerprint
                count = 0
                for row in dataset:
                    writer.writerow((config_name, row[SOURCE_TIME_COLUMN], *(row[name] for name in SOURCE_MODEL_COLUMNS)))
                    count += 1
                row_counts[config_name] = count

        combined_schema = [[name, source_schemas[name]] for name in EXPECTED_CONFIGS]
        manifest = {
            "dataset_id": DATASET_ID,
            "dataset_version": sha,
            "requested_revision": revision,
            "retrieved_at_utc": _utc_now().isoformat(),
            "license": SOURCE_LICENSE,
            "split": SOURCE_SPLIT,
            "available_configurations": list(available),
            "loaded_configurations": list(EXPECTED_CONFIGS),
            "row_counts": row_counts,
            "total_rows": sum(row_counts.values()),
            "source_schemas": source_schemas,
            "schema_fingerprints": schema_fingerprints,
            "combined_schema_fingerprint": _schema_fingerprint(combined_schema),
            "raw_columns": list(RAW_COLUMNS),
            "snapshot_sha256": _file_sha256(snapshot),
        }
        (stage / "source_manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        if run_dir.exists():
            raise FileExistsError(f"FuelCast run directory already exists: {run_dir}")
        os.rename(Path(staging_name), run_dir)

    return FuelCastSourceArtifact(
        snapshot_path=run_dir / "01_source" / "fuelcast_raw.csv",
        manifest_path=run_dir / "01_source" / "source_manifest.json",
        dataset_version=sha,
        row_counts=row_counts,
    )
