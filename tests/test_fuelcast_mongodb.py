"""Offline FuelCast persistence contract tests using a small in-memory collection."""

import copy
import csv
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from pymongo.errors import BulkWriteError

from greenfleet.constants.fuelcast import (
    CANONICAL_COLUMNS, CANONICAL_FEATURES, CANONICAL_UNITS, DATASET_ID,
    EXPECTED_CONFIGS, SOURCE_TO_CANONICAL,
)
from greenfleet.database.fuelcast import main, preflight_fuelcast_mongodb, run_fuelcast_mongodb
from greenfleet.pipeline.etl.fuelcast import _record_id

REVISION = "a" * 40


class Result:
    def __init__(self, matched, upserted):
        self.matched_count = matched
        self.modified_count = 0
        self.upserted_count = upserted


class Collection:
    def __init__(self):
        self.documents = []
        self.indexes = [{"name": "_id_", "key": {"_id": 1}, "unique": True}]
        self.batches = []
        self.fail_batch = False
        self.inject_post_conflict = False
        self.post_mutation = None
        self.post_count_override = None
        self.wrote = False

    def find(self, query):
        if query == {}:
            return iter(copy.deepcopy(self.documents))
        assert set(query) == {"record_id"}
        assert set(query["record_id"]) == {"$in"}
        ids = set(query["record_id"]["$in"])
        return iter(copy.deepcopy([doc for doc in self.documents if doc.get("record_id") in ids]))

    def count_documents(self, query):
        if self.wrote and query == {"dataset_version": REVISION} and self.post_count_override is not None:
            return self.post_count_override
        return sum(all(doc.get(k) == v for k, v in query.items()) for doc in self.documents)

    def list_indexes(self):
        return iter(copy.deepcopy(self.indexes))

    def create_index(self, keys, *, unique, name):
        self.indexes.append({"name": name, "key": dict(keys), "unique": unique})
        return name

    def bulk_write(self, operations, *, ordered):
        assert ordered is False
        self.batches.append(operations)
        matched = upserted = 0
        for operation in operations:
            key = operation._filter["record_id"]
            assert operation._doc.keys() == {"$setOnInsert"}
            assert operation._upsert is True
            if any(doc.get("record_id") == key for doc in self.documents):
                matched += 1
            else:
                self.documents.append(copy.deepcopy(operation._doc["$setOnInsert"]))
                upserted += 1
            if self.fail_batch and upserted:
                self.fail_batch = False
                raise BulkWriteError({"nMatched": matched, "nModified": 0,
                                      "nUpserted": upserted,
                                      "writeErrors": [{"errmsg": "mongodb://user:secret@host"}]})
        if self.inject_post_conflict:
            self.inject_post_conflict = False
            self.documents.append({"record_id": "concurrent-extra", "dataset_version": REVISION,
                                   "vessel_id": EXPECTED_CONFIGS[0], "time_index": 99})
        self.wrote = True
        if self.post_mutation is not None:
            self.post_mutation(self.documents)
        return Result(matched, upserted)


class Database:
    def __init__(self, collection):
        self.collection = collection

    def list_collection_names(self):
        return ["fuelcast_telemetry"]

    def __getitem__(self, name):
        assert name == "fuelcast_telemetry"
        return self.collection


class Client:
    def __init__(self, collection):
        self.database = Database(collection)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def list_database_names(self):
        return ["greenfleet"]

    def __getitem__(self, name):
        assert name == "greenfleet"
        return self.database


class FuelCastMongoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.run_dir = Path(self.temp.name) / "run"
        (self.run_dir / "02_etl").mkdir(parents=True)
        self.rows = []
        for vessel in EXPECTED_CONFIGS:
            row = {"record_id": _record_id(REVISION, vessel, 1), "dataset_version": REVISION,
                   "vessel_id": vessel, "time_index": 1, "fuel_consumption_kg_s": 1.5}
            row.update({name: 1.0 for name in CANONICAL_FEATURES})
            self.rows.append(row)
        self.rows[0]["wind_speed"] = None
        self.collection = Collection()
        self.client_patch = patch("greenfleet.database.fuelcast.MongoClient", return_value=Client(self.collection))
        self.mongo_client = self.client_patch.start()
        self.addCleanup(self.client_patch.stop)
        self.write()

    def write(self):
        csv_path = self.run_dir / "02_etl" / "fuelcast_clean.csv"
        with csv_path.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=CANONICAL_COLUMNS)
            writer.writeheader()
            writer.writerows(self.rows)
        audit = {"dataset_id": DATASET_ID, "source_run_id": "run", "dataset_version": REVISION,
                 "canonical_sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
                 "canonical_columns": list(CANONICAL_COLUMNS), "source_to_canonical": SOURCE_TO_CANONICAL,
                 "units": CANONICAL_UNITS,
                 "per_vessel": {v: {"output_rows": sum(r["vessel_id"] == v for r in self.rows)} for v in EXPECTED_CONFIGS},
                 "totals": {"output_rows": len(self.rows)}}
        (self.run_dir / "02_etl" / "etl_audit.json").write_text(json.dumps(audit))

    def apply(self, **kw):
        return run_fuelcast_mongodb(self.run_dir, uri="mongodb://user:secret@host", **kw)

    def report(self):
        return json.loads((self.run_dir / "03_mongodb" / "mongodb_load_report.json").read_text())

    def test_preflight_is_read_only_and_reports_counts(self):
        pre = preflight_fuelcast_mongodb(self.run_dir, uri="mongodb://example")
        self.assertTrue(pre.safe_to_apply)
        self.assertEqual(pre.collection_count, 0)
        self.assertEqual(len(pre.indexes_to_create), 3)
        self.assertEqual(len(self.collection.indexes), 1)
        self.assertEqual(self.collection.batches, [])

    def test_equivalent_indexes_are_reused_by_definition(self):
        self.collection.indexes.extend([
            {"name": "existing_id", "key": {"record_id": 1}, "unique": True,
             "sparse": False, "hidden": False, "background": True, "v": 2},
            {"name": "existing_version", "key": {"dataset_version": 1}, "unique": False,
             "sparse": False, "hidden": False, "ready": True},
            {"name": "existing_time", "key": {"vessel_id": 1, "time_index": 1}, "unique": False,
             "background": False, "ns": "greenfleet.fuelcast_telemetry"},
        ])
        pre = preflight_fuelcast_mongodb(self.run_dir, uri="mongodb://example")
        self.assertEqual(pre.indexes_to_create, [])
        self.assertEqual(len(pre.indexes_reused), 3)
        self.assertTrue(all(name.startswith("existing_") for name in pre.indexes_reused))
        self.apply()
        self.assertEqual(self.report()["indexes_created"], [])

    def test_duplicate_and_null_keys_block_load(self):
        self.collection.documents = [{"record_id": "other"}, {"record_id": "other"},
                                     {"record_id": None}]
        pre = preflight_fuelcast_mongodb(self.run_dir, uri="mongodb://example")
        self.assertEqual(pre.duplicate_record_id_count, 1)
        self.assertEqual(pre.null_record_id_count, 1)
        self.assertFalse(pre.safe_to_apply)
        with self.assertRaises(RuntimeError):
            self.apply()
        self.assertEqual(self.collection.batches, [])

    def test_first_load_and_idempotent_replay_preserve_extras(self):
        artifact = self.apply(batch_size=2)
        self.assertEqual(artifact.verified_loaded_rows, 3)
        self.assertEqual(self.report()["batch_progress"]["upserted"], 3)
        self.assertEqual(len(self.collection.indexes), 4)
        self.assertEqual(len(self.collection.batches), 2)
        doc = self.collection.documents[0]
        self.assertIsNone(doc["wind_speed"])
        self.assertIs(type(doc["time_index"]), int)
        self.assertIs(type(doc["fuel_consumption_kg_s"]), float)
        self.assertEqual(set(doc), set(CANONICAL_COLUMNS))
        doc["operator_note"] = "keep"
        self.apply()
        self.assertEqual(self.report()["batch_progress"]["upserted"], 0)
        self.assertEqual(self.report()["batch_progress"]["modified"], 0)
        self.assertEqual(doc["operator_note"], "keep")

    def test_partial_existing_and_other_version_untouched(self):
        self.collection.documents = [copy.deepcopy(self.rows[0]),
                                     {"record_id": "other", "dataset_version": "b" * 40}]
        self.apply()
        self.assertEqual(self.report()["batch_progress"]["upserted"], 2)
        self.assertEqual(self.collection.documents[1]["record_id"], "other")

    def test_preflight_conflicts_block_writes(self):
        for document in (dict(self.rows[0], fuel_consumption_kg_s=999),
                         {"record_id": "extra", "dataset_version": REVISION},
                         {"dataset_version": "other"}):
            with self.subTest(document=document):
                self.collection.documents = [document]
                with self.assertRaises(RuntimeError):
                    self.apply()
                self.assertEqual(self.collection.batches, [])
                self.assertEqual(self.report()["failure"]["stage"], "preflight")

    def test_canonical_field_presence_and_exact_types(self):
        variants = []
        missing_null = copy.deepcopy(self.rows[0])
        missing_null.pop("wind_speed")
        variants.append(missing_null)
        wrong_time = copy.deepcopy(self.rows[0])
        wrong_time["time_index"] = True
        variants.append(wrong_time)
        wrong_float = copy.deepcopy(self.rows[0])
        wrong_float["fuel_consumption_kg_s"] = 1
        variants.append(wrong_float)
        wrong_feature = copy.deepcopy(self.rows[0])
        wrong_feature["speed_over_ground"] = True
        variants.append(wrong_feature)
        for document in variants:
            with self.subTest(document=document):
                self.collection.documents = [document]
                pre = preflight_fuelcast_mongodb(self.run_dir, uri="mongodb://example")
                self.assertEqual(pre.canonical_conflicts, 1)
                with self.assertRaises(RuntimeError):
                    self.apply()
                self.assertEqual(self.collection.batches, [])


    def test_index_conflict_blocks_all_writes(self):
        self.collection.indexes.append({"name": "bad", "key": {"record_id": 1}, "unique": False})
        with self.assertRaises(RuntimeError):
            self.apply()
        self.assertEqual(self.collection.batches, [])

    def test_partial_index_with_matching_keys_is_not_equivalent(self):
        self.collection.indexes.append({"name": "partial_record_id", "key": {"record_id": 1},
                                        "unique": True, "partialFilterExpression": {"record_id": {"$exists": True}}})
        with self.assertRaises(RuntimeError):
            self.apply()
        self.assertEqual(self.report()["preflight"]["blocking_reasons"], ["conflicting_index_definition"])
        self.assertEqual(self.collection.batches, [])

    def test_optioned_indexes_block_reuse_and_sanitize_values(self):
        variants = [
            {"sparse": True},
            {"collation": {"locale": "mongodb://user:secret@host"}},
            {"expireAfterSeconds": 60},
            {"hidden": True},
            {"operatorSecret": "mongodb://user:secret@host"},
        ]
        for options in variants:
            with self.subTest(options=options):
                self.collection.indexes = [{"name": "_id_", "key": {"_id": 1}, "unique": True},
                    {"name": "mongodb://user:secret@host", "key": {"record_id": 1},
                     "unique": True, **options}]
                pre = preflight_fuelcast_mongodb(self.run_dir, uri="mongodb://example")
                self.assertFalse(pre.safe_to_apply)
                serialized = json.dumps(pre.to_dict())
                self.assertNotIn("secret", serialized)
                self.assertNotIn("mongodb://", serialized)
                with self.assertRaises(RuntimeError):
                    self.apply()
                self.assertNotIn("secret", json.dumps(self.report()))
                self.assertEqual(self.collection.batches, [])

    def test_source_rejection_before_connection(self):
        cases = [lambda: self.rows[0].update(record_id="bad"),
                 lambda: self.rows[0].update(time_index="1.5"),
                 lambda: self.rows[0].update(wind_speed="inf"),
                 lambda: self.rows[0].update(fuel_consumption_kg_s="-1"),
                 lambda: self.rows[0].update(dataset_version="b" * 40),
                 lambda: self.rows[0].update(vessel_id="unknown")]
        for mutate in cases:
            with self.subTest(mutate=mutate):
                original = copy.deepcopy(self.rows)
                mutate()
                self.write()
                self.mongo_client.reset_mock()
                with self.assertRaises(RuntimeError):
                    self.apply()
                self.mongo_client.assert_not_called()
                self.rows = original
                self.write()
        audit_path = self.run_dir / "02_etl" / "etl_audit.json"
        audit_path.write_text(audit_path.read_text().replace(DATASET_ID, "wrong"))
        self.mongo_client.reset_mock()
        with self.assertRaises(RuntimeError):
            self.apply()
        self.mongo_client.assert_not_called()

    def test_hash_schema_count_and_duplicate_rejection_before_connection(self):
        csv_path = self.run_dir / "02_etl" / "fuelcast_clean.csv"
        audit_path = self.run_dir / "02_etl" / "etl_audit.json"
        valid_csv, valid_audit = csv_path.read_bytes(), audit_path.read_bytes()
        mutations = [
            (lambda: csv_path.write_bytes(valid_csv + b"\n")),
            (lambda: audit_path.write_text(valid_audit.decode().replace('"output_rows": 3', '"output_rows": 4'))),
            (lambda: self.rows.append(copy.deepcopy(self.rows[0]))),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                mutate()
                if len(self.rows) > 3:
                    self.write()
                self.mongo_client.reset_mock()
                with self.assertRaises(RuntimeError):
                    self.apply()
                self.mongo_client.assert_not_called()
                self.rows = self.rows[:3]
                csv_path.write_bytes(valid_csv)
                audit_path.write_bytes(valid_audit)

    def test_header_and_per_vessel_audit_mismatch_before_connection(self):
        csv_path = self.run_dir / "02_etl" / "fuelcast_clean.csv"
        audit_path = self.run_dir / "02_etl" / "etl_audit.json"
        valid_csv, valid_audit = csv_path.read_bytes(), audit_path.read_bytes()
        invalid_csv = valid_csv.replace(b"wind_speed", b"Wind_speed", 1)
        csv_path.write_bytes(invalid_csv)
        audit = json.loads(valid_audit)
        audit["canonical_sha256"] = hashlib.sha256(invalid_csv).hexdigest()
        audit_path.write_text(json.dumps(audit))
        self.mongo_client.reset_mock()
        with self.assertRaises(RuntimeError):
            self.apply()
        self.mongo_client.assert_not_called()
        csv_path.write_bytes(valid_csv)
        audit = json.loads(valid_audit)
        audit["per_vessel"][EXPECTED_CONFIGS[0]]["output_rows"] = 2
        audit["per_vessel"][EXPECTED_CONFIGS[1]]["output_rows"] = 0
        audit_path.write_text(json.dumps(audit))
        self.mongo_client.reset_mock()
        with self.assertRaises(RuntimeError):
            self.apply()
        self.mongo_client.assert_not_called()

    def test_bson_int64_overflow_rejected_before_connection(self):
        huge_time = 1 << 63
        vessel = EXPECTED_CONFIGS[0]
        self.rows[0]["time_index"] = huge_time
        self.rows[0]["record_id"] = _record_id(REVISION, vessel, huge_time)
        self.write()  # Recomputes a matching canonical CSV hash and audit.
        self.mongo_client.reset_mock()
        with self.assertRaisesRegex(RuntimeError, "source_validation"):
            self.apply()
        self.mongo_client.assert_not_called()
        report = self.report()
        self.assertEqual(report["failure"],
                         {"stage": "source_validation", "type": "ValueError"})
        self.assertNotIn("secret", json.dumps(report))

    def test_partial_bulk_failure_report_is_safe_and_replayable(self):
        self.collection.fail_batch = True
        with self.assertRaisesRegex(RuntimeError, "bulk_write"):
            self.apply(batch_size=1)
        self.assertNotIn("secret", json.dumps(self.report()))
        self.assertNotIn("host", json.dumps(self.report()))
        self.assertEqual(self.report()["batch_progress"]["completed_batches"], 0)
        self.assertEqual(self.report()["batch_progress"]["upserted"], 1)
        self.apply(batch_size=1)
        self.assertEqual(self.report()["batch_progress"]["upserted"], 2)

    def test_post_verification_detects_concurrent_extra_record(self):
        self.collection.inject_post_conflict = True
        with self.assertRaisesRegex(RuntimeError, "post_verification"):
            self.apply()
        self.assertEqual(self.report()["failure"]["stage"], "post_verification")
        self.assertEqual(self.report()["post_verification"]["extra_active_version_ids"], 1)

    def test_post_verification_rejects_each_required_invariant(self):
        cases = [
            ("total", lambda documents: None, "active_version_count", 4),
            ("vessel_count", lambda documents: documents[0].update(vessel_id="other"),
             "active_version_per_vessel", None),
            ("membership", lambda documents: documents.pop(), "expected_ids_present", 2),
            ("content", lambda documents: documents[0].update(fuel_consumption_kg_s=9.0),
             "canonical_conflicts", 1),
            ("duplicate_time", lambda documents: documents.append({
                "record_id": "concurrent-time", "dataset_version": REVISION,
                "vessel_id": EXPECTED_CONFIGS[0], "time_index": 1}),
             "blocking_reasons", "duplicate_active_vessel_time"),
        ]
        for label, mutation, field, expected in cases:
            with self.subTest(label=label):
                self.collection.__init__()
                self.collection.post_mutation = mutation
                if label == "total":
                    self.collection.post_count_override = 4
                with self.assertRaisesRegex(RuntimeError, "post_verification"):
                    self.apply()
                verification = self.report()["post_verification"]
                self.assertEqual(self.report()["failure"]["stage"], "post_verification")
                if label == "vessel_count":
                    self.assertNotEqual(verification[field], {v: 1 for v in EXPECTED_CONFIGS})
                elif label == "duplicate_time":
                    self.assertIn(expected, verification[field])
                else:
                    self.assertEqual(verification[field], expected)

    def test_cli_error_output_never_contains_uri_or_driver_text(self):
        uri = "mongodb://user:secret@host"
        stdout, stderr = io.StringIO(), io.StringIO()
        args = ["fuelcast", "--run-id", "run", "--artifacts-root", self.temp.name]
        with patch.dict(os.environ, {"MONGODB_URI": uri}), \
             patch.object(sys, "argv", args), \
             patch("greenfleet.database.fuelcast.MongoClient",
                   side_effect=RuntimeError(f"driver failed at {uri}")), \
             redirect_stdout(stdout), redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as raised:
                main()
        self.assertEqual(raised.exception.code, 1)
        output = stdout.getvalue() + stderr.getvalue()
        self.assertNotIn(uri, output)
        self.assertNotIn("secret", output)
        self.assertNotIn("driver failed", output)

    def test_destination_names_reject_uri_text_before_connection_or_report(self):
        unsafe = "mongodb://user:secret@host"
        for options in ({"database": unsafe}, {"collection": unsafe}):
            with self.subTest(options=options):
                self.mongo_client.reset_mock()
                with self.assertRaises(ValueError):
                    preflight_fuelcast_mongodb(self.run_dir, uri="mongodb://example", **options)
                self.mongo_client.assert_not_called()
                with self.assertRaisesRegex(RuntimeError, "destination_validation"):
                    self.apply(**options)
                self.mongo_client.assert_not_called()
                report = json.dumps(self.report())
                self.assertNotIn(unsafe, report)
                self.assertNotIn("secret", report)
                self.assertIn("<invalid>", report)
        pre = preflight_fuelcast_mongodb(self.run_dir, uri="mongodb://example")
        self.assertEqual(pre.destination,
                         {"database": "greenfleet", "collection": "fuelcast_telemetry"})

    def test_atomic_report_replacement_after_failure(self):
        self.apply()
        report_path = self.run_dir / "03_mongodb" / "mongodb_load_report.json"
        self.collection.documents.append({"record_id": "extra", "dataset_version": REVISION})
        with self.assertRaises(RuntimeError):
            self.apply()
        self.assertEqual(json.loads(report_path.read_text())["status"], "failed")
        self.assertEqual(list(report_path.parent.glob("*.tmp")), [])

    def test_report_replace_failure_preserves_previous_bytes(self):
        self.apply()
        report_path = self.run_dir / "03_mongodb" / "mongodb_load_report.json"
        original = report_path.read_bytes()
        with patch("greenfleet.database.fuelcast.os.replace", side_effect=OSError("disk unavailable")):
            with self.assertRaises(OSError):
                self.apply()
        self.assertEqual(report_path.read_bytes(), original)
        self.assertEqual(list(report_path.parent.glob(".mongodb_load_report-*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
