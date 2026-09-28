"""Validated, idempotent persistence of a pinned FuelCast canonical snapshot."""

import argparse
import csv
import hashlib
import io
import json
import math
import os
import re
import tempfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from importlib.metadata import version
from pathlib import Path

from pymongo import MongoClient, UpdateOne
from pymongo.errors import BulkWriteError

from greenfleet.artifacts.fuelcast_mongodb_artifact import FuelCastMongoArtifact
from greenfleet.constants.fuelcast import (
    CANONICAL_COLUMNS, CANONICAL_FEATURES, CANONICAL_TARGET, CANONICAL_UNITS,
    DATASET_ID, EXPECTED_CONFIGS, MONGODB_COLLECTION, MONGODB_DATABASE,
    MONGODB_INDEXES, SOURCE_TO_CANONICAL,
)
from greenfleet.constants.training_pipeline_constants import ARTIFACTS_DIR
from greenfleet.pipeline.etl.fuelcast import _record_id


def _utc():
    return datetime.now(timezone.utc).isoformat()


def _fail(message):
    raise ValueError(message)


def _number(value, *, optional=False):
    if optional and value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        _fail("Canonical CSV contains a nonnumeric value")
    if not math.isfinite(number):
        _fail("Canonical CSV contains a nonfinite value")
    return number


def _snapshot(run_dir):
    """Capture both source files before any network access or database mutation."""
    csv_bytes = (run_dir / "02_etl" / "fuelcast_clean.csv").read_bytes()
    audit_bytes = (run_dir / "02_etl" / "etl_audit.json").read_bytes()
    audit = json.loads(audit_bytes.decode("utf-8"))
    csv_hash = hashlib.sha256(csv_bytes).hexdigest()
    revision = audit.get("dataset_version")
    if (audit.get("dataset_id") != DATASET_ID or audit.get("source_run_id") != run_dir.name
            or not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision)
            or audit.get("canonical_sha256") != csv_hash
            or audit.get("canonical_columns") != list(CANONICAL_COLUMNS)
            or audit.get("source_to_canonical") != SOURCE_TO_CANONICAL
            or audit.get("units") != CANONICAL_UNITS):
        _fail("FuelCast canonical audit mismatch")
    expected = audit.get("per_vessel")
    if not isinstance(expected, dict) or set(expected) != set(EXPECTED_CONFIGS):
        _fail("FuelCast audit vessel mismatch")
    expected_counts = {}
    for vessel in EXPECTED_CONFIGS:
        count = expected[vessel].get("output_rows") if isinstance(expected[vessel], dict) else None
        if type(count) is not int or count <= 0:
            _fail("FuelCast audit row count mismatch")
        expected_counts[vessel] = count
    totals = audit.get("totals")
    if not isinstance(totals, dict) or totals.get("output_rows") != sum(expected_counts.values()):
        _fail("FuelCast audit total mismatch")
    documents = []
    counts = Counter()
    ids, keys = set(), set()
    previous_key = None
    with io.StringIO(csv_bytes.decode("utf-8"), newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != list(CANONICAL_COLUMNS):
            _fail("FuelCast canonical column order mismatch")
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                _fail("FuelCast malformed canonical CSV row")
            vessel = row["vessel_id"]
            if vessel not in EXPECTED_CONFIGS or row["dataset_version"] != revision:
                _fail("FuelCast canonical vessel or version mismatch")
            try:
                decimal_time = Decimal(row["time_index"])
            except InvalidOperation:
                _fail("FuelCast invalid time index")
            if not decimal_time.is_finite() or decimal_time < 0 or decimal_time != decimal_time.to_integral_value():
                _fail("FuelCast invalid time index")
            time_index = int(decimal_time)
            if time_index > (1 << 63) - 1:
                _fail("FuelCast time index exceeds BSON int64 range")
            if row["time_index"] != str(time_index):
                _fail("FuelCast noncanonical time index")
            record_id = _record_id(revision, vessel, time_index)
            if row["record_id"] != record_id:
                _fail("FuelCast record ID mismatch")
            key = (vessel, time_index)
            if record_id in ids or key in keys:
                _fail("FuelCast duplicate canonical key")
            if previous_key is not None and key <= previous_key:
                _fail("FuelCast canonical sort mismatch")
            ids.add(record_id)
            keys.add(key)
            previous_key = key
            target = _number(row[CANONICAL_TARGET])
            if target < 0:
                _fail("FuelCast invalid target")
            doc = {"record_id": record_id, "dataset_version": revision,
                   "vessel_id": vessel, "time_index": time_index}
            for name in CANONICAL_FEATURES:
                value = _number(row[name], optional=True)
                if value is not None and ((name == "wind_direction" and not 0 <= value <= 360)
                        or (name == "wave_period" and value <= 0)
                        or (name != "wind_direction" and name != "wave_period" and value < 0)):
                    _fail("FuelCast invalid feature range")
                doc[name] = value
            doc[CANONICAL_TARGET] = target
            documents.append(doc)
            counts[vessel] += 1
    if dict(counts) != expected_counts:
        _fail("FuelCast canonical row counts mismatch")
    source = {"dataset_id": DATASET_ID, "source_run_id": run_dir.name,
              "dataset_version": revision, "canonical_sha256": csv_hash,
              "audit_sha256": hashlib.sha256(audit_bytes).hexdigest(),
              "canonical_columns": list(CANONICAL_COLUMNS), "row_counts": expected_counts,
              "total_rows": len(documents)}
    return documents, source


def _safe_indexes(collection):
    indexes = []
    for index in collection.list_indexes():
        keys = list(index["key"].items())
        raw_name = index["name"]
        required_names = {"_id_", *(entry[0] for entry in MONGODB_INDEXES)}
        safe_name = (raw_name if raw_name in required_names else
                     "existing_" + hashlib.sha256(str(raw_name).encode("utf-8")).hexdigest()[:12])
        allowed_fields = set(CANONICAL_COLUMNS) | {"_id"}
        safe_keys = [[field if field in allowed_fields else "<other>",
                      direction if type(direction) is int and direction in (1, -1) else "<other>"]
                     for field, direction in keys]
        other_options = any(option not in {
            "v", "key", "name", "unique", "sparse", "partialFilterExpression",
            "collation", "expireAfterSeconds", "hidden", "background", "ns",
            "buildUUID", "ready",
        } for option in index)
        indexes.append({"name": safe_name, "key": safe_keys,
                        "unique": bool(index.get("unique", False)),
                        "sparse": bool(index.get("sparse", False)),
                        "partial": "partialFilterExpression" in index,
                        "collation": "collation" in index,
                        "ttl": "expireAfterSeconds" in index,
                        "hidden": bool(index.get("hidden", False)),
                        "other_options": other_options})
    return indexes


def _index_plan(indexes):
    created, reused, conflicts = [], [], []
    for name, keys, unique in MONGODB_INDEXES:
        same_keys = [i for i in indexes if i["key"] == [list(k) for k in keys]]
        equivalent = [i for i in same_keys if
                      i["unique"] == unique and not i["sparse"]
                      and not i["partial"] and not i["collation"]
                      and not i["ttl"] and not i["hidden"] and not i["other_options"]]
        if any(i not in equivalent for i in same_keys) or any(
                i["name"] == name and i not in equivalent for i in indexes):
            conflicts.append(name)
        elif equivalent:
            reused.append(equivalent[0]["name"])
        else:
            created.append(name)
    return created, reused, conflicts


@dataclass(frozen=True)
class FuelCastMongoPreflight:
    source: dict
    destination: dict
    database_exists: bool
    collection_exists: bool
    collection_count: int
    active_version_count: int
    active_version_per_vessel: dict
    indexes: list
    indexes_to_create: list
    indexes_reused: list
    missing_record_id_count: int
    null_record_id_count: int
    duplicate_record_id_count: int
    expected_ids_present: int
    canonical_conflicts: int
    extra_active_version_ids: int
    blocking_reasons: list

    @property
    def safe_to_apply(self):
        return not self.blocking_reasons

    def to_dict(self):
        return dict(self.__dict__, safe_to_apply=self.safe_to_apply)


def _inspect(client, database, collection, documents, source):
    db_names = client.list_database_names()
    db_exists = database in db_names
    db = client[database]
    collection_exists = db_exists and collection in db.list_collection_names()
    target = db[collection]
    expected = {doc["record_id"]: doc for doc in documents}
    indexes = _safe_indexes(target) if collection_exists else []
    to_create, reused, conflicts = _index_plan(indexes)
    # A full read detects unsafe keys even outside this dataset version.
    present, active_counts = set(), Counter()
    seen_ids, seen_active_keys = set(), set()
    missing_keys = null_keys = duplicate_ids = canonical_conflicts = extras = duplicate_active_keys = 0
    for existing in target.find({}) if collection_exists else ():
        record_id = existing.get("record_id")
        if "record_id" not in existing:
            missing_keys += 1
        elif record_id is None:
            null_keys += 1
        elif record_id in seen_ids:
            duplicate_ids += 1
        else:
            seen_ids.add(record_id)
        if existing.get("dataset_version") == source["dataset_version"]:
            active_counts[existing.get("vessel_id")] += 1
            if record_id not in expected:
                extras += 1
            key = (existing.get("vessel_id"), existing.get("time_index"))
            if key in seen_active_keys:
                duplicate_active_keys += 1
            seen_active_keys.add(key)
    if collection_exists:
        expected_ids = list(expected)
        for start in range(0, len(expected_ids), 1000):
            batch_ids = expected_ids[start:start + 1000]
            for existing in target.find({"record_id": {"$in": batch_ids}}):
                record_id = existing["record_id"]
                present.add(record_id)
                if any(field not in existing or type(existing[field]) is not type(value)
                       or existing[field] != value
                       for field, value in expected[record_id].items()):
                    canonical_conflicts += 1
    reasons = []
    for label, count in (("missing_record_id", missing_keys), ("null_record_id", null_keys),
                         ("duplicate_record_id", duplicate_ids),
                         ("canonical_conflict", canonical_conflicts), ("extra_active_version_id", extras),
                         ("duplicate_active_vessel_time", duplicate_active_keys)):
        if count:
            reasons.append(label)
    if conflicts:
        reasons.append("conflicting_index_definition")
    return FuelCastMongoPreflight(source, {"database": database, "collection": collection},
        db_exists, collection_exists, target.count_documents({}) if collection_exists else 0,
        target.count_documents({"dataset_version": source["dataset_version"]}) if collection_exists else 0,
        {v: active_counts[v] for v in EXPECTED_CONFIGS}, indexes, to_create, reused,
        missing_keys, null_keys, duplicate_ids, len(present), canonical_conflicts, extras, reasons)


def _uri(uri):
    value = uri if uri is not None else os.environ.get("MONGODB_URI")
    if not value:
        _fail("MONGODB_URI is required")
    return value


def _safe_destination_name(value):
    """Accept a conservative MongoDB name subset with no URI punctuation."""
    if isinstance(value, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]{0,127}", value):
        return value
    return None


def _validate_destination(database, collection):
    if _safe_destination_name(database) is None or _safe_destination_name(collection) is None:
        _fail("Invalid FuelCast MongoDB destination name")


def preflight_fuelcast_mongodb(run_dir: Path, *, uri: str | None = None,
                                database: str = MONGODB_DATABASE,
                                collection: str = MONGODB_COLLECTION) -> FuelCastMongoPreflight:
    _validate_destination(database, collection)
    documents, source = _snapshot(Path(run_dir))
    with MongoClient(_uri(uri), serverSelectionTimeoutMS=10_000) as client:
        return _inspect(client, database, collection, documents, source)


def _atomic_report(path, report):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                         prefix=".mongodb_load_report-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(report, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def _partial_bulk_counts(details, batch_length):
    """Keep only bounded numeric progress from a failed unordered write."""
    if not isinstance(details, dict):
        return {"matched": 0, "modified": 0, "upserted": 0}
    counts = {}
    for report_key, driver_key in (("matched", "nMatched"),
                                   ("modified", "nModified"),
                                   ("upserted", "nUpserted")):
        value = details.get(driver_key)
        counts[report_key] = value if type(value) is int and 0 <= value <= batch_length else 0
    return counts


def run_fuelcast_mongodb(run_dir: Path, *, uri: str | None = None,
                         database: str = MONGODB_DATABASE, collection: str = MONGODB_COLLECTION,
                         batch_size: int = 1000) -> FuelCastMongoArtifact:
    run_dir = Path(run_dir)
    report_path = run_dir / "03_mongodb" / "mongodb_load_report.json"
    report = {"status": "failed", "started_at_utc": _utc(),
              "destination": {"database": _safe_destination_name(database) or "<invalid>",
                              "collection": _safe_destination_name(collection) or "<invalid>"},
              "source": None, "preflight": None, "indexes_created": [], "indexes_reused": [],
              "batch_progress": {"completed_batches": 0, "matched": 0, "modified": 0, "upserted": 0},
              "post_verification": None, "dependency_versions": {"pymongo": version("pymongo")}}
    stage = "destination_validation"
    try:
        _validate_destination(database, collection)
        stage = "source_validation"
        if type(batch_size) is not int or batch_size < 1:
            _fail("batch_size must be positive")
        documents, source = _snapshot(run_dir)
        report["source"] = source
        stage = "preflight"
        with MongoClient(_uri(uri), serverSelectionTimeoutMS=10_000) as client:
            preflight = _inspect(client, database, collection, documents, source)
            report["preflight"] = preflight.to_dict()
            if not preflight.safe_to_apply:
                _fail("FuelCast MongoDB preflight blocked")
            target = client[database][collection]
            stage = "indexes"
            report["indexes_reused"] = preflight.indexes_reused
            for name, keys, unique in MONGODB_INDEXES:
                if name in preflight.indexes_to_create:
                    target.create_index(list(keys), unique=unique, name=name)
                    report["indexes_created"].append(name)
            stage = "bulk_write"
            progress = report["batch_progress"]
            for start in range(0, len(documents), batch_size):
                operations = [UpdateOne({"record_id": doc["record_id"]},
                                        {"$setOnInsert": doc}, upsert=True)
                              for doc in documents[start:start + batch_size]]
                try:
                    result = target.bulk_write(operations, ordered=False)
                except BulkWriteError as exc:
                    partial = _partial_bulk_counts(exc.details, len(operations))
                    for key, value in partial.items():
                        progress[key] += value
                    raise
                progress["completed_batches"] += 1
                progress["matched"] += result.matched_count
                progress["modified"] += result.modified_count
                progress["upserted"] += result.upserted_count
            stage = "post_verification"
            verification = _inspect(client, database, collection, documents, source)
            report["post_verification"] = verification.to_dict()
            if (verification.blocking_reasons or verification.active_version_count != len(documents)
                    or verification.active_version_per_vessel != source["row_counts"]
                    or verification.expected_ids_present != len(documents)
                    or verification.indexes_to_create):
                _fail("FuelCast MongoDB post-verification failed")
            report["status"] = "success"
    except Exception as exc:
        report["failure"] = {"stage": stage, "type": type(exc).__name__}
        raise RuntimeError(f"FuelCast MongoDB {stage} failed; see sanitized load report") from None
    finally:
        report["finished_at_utc"] = _utc()
        _atomic_report(report_path, report)
    return FuelCastMongoArtifact(report_path, "success", source["dataset_version"],
                                 len(documents), report["post_verification"]["active_version_count"])


def main():
    parser = argparse.ArgumentParser(description="Preflight or apply a canonical FuelCast MongoDB load")
    parser.add_argument("--run-id", required=True, help="Existing FuelCast run ID")
    parser.add_argument("--artifacts-root", type=Path, default=ARTIFACTS_DIR)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--preflight-only", action="store_true", help="Read-only validation (default)")
    mode.add_argument("--apply", action="store_true", help="Create indexes and idempotently upsert")
    parser.add_argument("--database", default=MONGODB_DATABASE)
    parser.add_argument("--collection", default=MONGODB_COLLECTION)
    parser.add_argument("--batch-size", type=int, default=1000)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", args.run_id) or args.run_id in {".", ".."}:
        parser.error("--run-id must be a single safe directory name")
    try:
        run_dir = args.artifacts_root / args.run_id
        if args.apply:
            artifact = run_fuelcast_mongodb(run_dir, database=args.database,
                collection=args.collection, batch_size=args.batch_size)
            print(json.dumps({"status": artifact.status, "report_path": str(artifact.report_path),
                              "verified_loaded_rows": artifact.verified_loaded_rows}))
        else:
            result = preflight_fuelcast_mongodb(run_dir, database=args.database, collection=args.collection)
            print(json.dumps(result.to_dict(), indent=2))
    except Exception:
        parser.exit(1, "FuelCast MongoDB operation failed; inspect source and sanitized report\n")


if __name__ == "__main__":
    main()
