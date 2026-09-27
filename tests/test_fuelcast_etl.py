"""Offline contract tests for the FuelCast canonical ETL stage."""

import csv
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from greenfleet.constants.fuelcast import (
    CANONICAL_COLUMNS, DATASET_ID, EXPECTED_CONFIGS, RAW_COLUMNS,
    SOURCE_LICENSE, SOURCE_MODEL_COLUMNS, SOURCE_SPLIT,
)
from greenfleet.pipeline.etl.fuelcast import _fingerprint, _sha256, run_fuelcast_etl


REVISION = "a" * 40


def make_row(vessel, time, target="1.5", **features):
    row = dict(zip(RAW_COLUMNS, (vessel, time, 2, 3, 90, 4, 5, 6, target)))
    row.update(features)
    return row


class FuelCastETLTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.run_dir = Path(self.temp.name) / "run"
        self.source = self.run_dir / "01_source"
        self.source.mkdir(parents=True)
        self.rows = [make_row(vessel, "1") for vessel in EXPECTED_CONFIGS]
        self.write_source()

    def write_source(self):
        snapshot = self.source / "fuelcast_raw.csv"
        with snapshot.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, RAW_COLUMNS)
            writer.writeheader()
            writer.writerows(self.rows)
        schema = [["index", "int64"], *[[name, "double"] for name in SOURCE_MODEL_COLUMNS]]
        schemas = {vessel: schema for vessel in EXPECTED_CONFIGS}
        counts = {vessel: sum(row["vessel_id"] == vessel for row in self.rows) for vessel in EXPECTED_CONFIGS}
        self.manifest = {
            "dataset_id": DATASET_ID, "dataset_version": REVISION,
            "license": SOURCE_LICENSE, "split": SOURCE_SPLIT,
            "retrieved_at_utc": "2026-09-28T00:00:00+00:00",
            "loaded_configurations": list(EXPECTED_CONFIGS),
            "raw_columns": list(RAW_COLUMNS), "row_counts": counts,
            "total_rows": len(self.rows), "source_schemas": schemas,
            "schema_fingerprints": {v: _fingerprint(schema) for v in EXPECTED_CONFIGS},
            "combined_schema_fingerprint": _fingerprint([[v, schema] for v in EXPECTED_CONFIGS]),
            "snapshot_sha256": _sha256(snapshot),
        }
        self.write_manifest()

    def write_manifest(self):
        (self.source / "source_manifest.json").write_text(json.dumps(self.manifest), encoding="utf-8")

    def assert_no_stage(self):
        self.assertFalse((self.run_dir / "02_etl").exists())

    def test_canonical_order_ids_and_reproducible_bytes(self):
        self.rows += [make_row(EXPECTED_CONFIGS[0], "0")]
        self.write_source()
        result = run_fuelcast_etl(self.run_dir)
        with result.canonical_path.open(newline="") as stream:
            reader = csv.DictReader(stream)
            self.assertEqual(reader.fieldnames, list(CANONICAL_COLUMNS))
            rows = list(reader)
        self.assertEqual([(r["vessel_id"], r["time_index"]) for r in rows],
                         [(EXPECTED_CONFIGS[0], "0"), (EXPECTED_CONFIGS[0], "1"),
                          (EXPECTED_CONFIGS[1], "1"), (EXPECTED_CONFIGS[2], "1")])
        self.assertEqual(len({r["record_id"] for r in rows}), len(rows))
        self.assertTrue(all(len(r["record_id"]) == 64 for r in rows))
        self.assertEqual(set(r["dataset_version"] for r in rows), {REVISION})
        first_bytes = result.canonical_path.read_bytes()
        self.assertEqual(_sha256(result.canonical_path), json.loads(result.audit_path.read_text())["canonical_sha256"])
        with self.assertRaises(FileExistsError):
            run_fuelcast_etl(self.run_dir)
        other = Path(self.temp.name) / "other"
        (other / "01_source").mkdir(parents=True)
        for name in ("fuelcast_raw.csv", "source_manifest.json"):
            (other / "01_source" / name).write_bytes((self.source / name).read_bytes())
        self.assertEqual(first_bytes, run_fuelcast_etl(other).canonical_path.read_bytes())

    def test_target_time_and_duplicate_audit_reconciles(self):
        vessel = EXPECTED_CONFIGS[0]
        self.rows += [dict(self.rows[0]), make_row(vessel, "2", ""),
                      make_row(vessel, "3", "bad"), make_row(vessel, "4", "inf"),
                      make_row(vessel, "5", "-1"), make_row(vessel, "", "1"),
                      make_row(vessel, "-1", "1"), make_row(vessel, "1.5", "1")]
        self.write_source()
        result = run_fuelcast_etl(self.run_dir)
        audit = json.loads(result.audit_path.read_text())
        vessel_audit = audit["per_vessel"][vessel]
        self.assertEqual(vessel_audit["exact_duplicates_removed"], 1)
        self.assertEqual(vessel_audit["invalid_targets_removed"],
                         {"missing": 1, "nonnumeric": 1, "nonfinite": 1, "negative": 1})
        self.assertEqual(vessel_audit["invalid_times_removed"],
                         {"missing": 1, "negative": 1, "nonintegral": 1})
        self.assertEqual(audit["totals"]["input_rows"], audit["totals"]["output_rows"] +
                         audit["totals"]["exact_duplicates_removed"] +
                         audit["totals"]["invalid_targets_removed"] +
                         audit["totals"]["invalid_times_removed"])

    def test_twelve_missing_time_rows_are_dropped(self):
        self.rows += [make_row(EXPECTED_CONFIGS[1], "", "1") for _ in range(4)]
        self.rows += [make_row(EXPECTED_CONFIGS[2], "", str(i)) for i in range(8)]
        self.write_source()
        audit = json.loads(run_fuelcast_etl(self.run_dir).audit_path.read_text())
        self.assertEqual(audit["totals"]["invalid_times_removed"], 9)
        self.assertEqual(audit["totals"]["exact_duplicates_removed"], 3)

    def test_feature_nulls_coercions_and_ranges(self):
        self.rows[0]["Ship_SpeedOverGround"] = "bad"
        self.rows[0]["Weather_WindSpeed10M"] = "inf"
        self.rows[0]["Weather_WindDirection10M"] = "361"
        self.rows[0]["Weather_WaveHeight"] = ""
        self.rows[0]["Weather_WavePeriod"] = "0"
        self.rows[0]["Weather_OceanCurrentVelocity"] = "-1"
        self.write_source()
        result = run_fuelcast_etl(self.run_dir)
        with result.canonical_path.open(newline="") as stream:
            row = next(csv.DictReader(stream))
        self.assertTrue(all(row[feature] == "" for feature in (
            "speed_over_ground", "wind_speed", "wind_direction", "wave_height",
            "wave_period", "current_speed")))
        audit = json.loads(result.audit_path.read_text())["per_vessel"][EXPECTED_CONFIGS[0]]
        self.assertEqual(audit["feature_coercions"]["speed_over_ground"], {"nonnumeric": 1})
        self.assertEqual(audit["feature_range_violations"],
                         {"wind_direction": 1, "wave_period": 1, "current_speed": 1})

    def test_conflicting_key_fails_without_partial_output(self):
        self.rows.append(make_row(EXPECTED_CONFIGS[0], "1", "2"))
        self.write_source()
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            run_fuelcast_etl(self.run_dir)
        self.assert_no_stage()

    def test_empty_canonical_vessel_fails(self):
        self.rows[0]["Consumer_Total_MomentaryFuel"] = ""
        self.write_source()
        with self.assertRaisesRegex(ValueError, "no valid canonical rows"):
            run_fuelcast_etl(self.run_dir)
        self.assert_no_stage()

    def test_existing_empty_output_directory_is_not_replaced(self):
        output = self.run_dir / "02_etl"
        output.mkdir()
        with self.assertRaises(FileExistsError):
            run_fuelcast_etl(self.run_dir)
        self.assertTrue(output.is_dir())
        self.assertEqual(list(output.iterdir()), [])

    def test_publish_race_keeps_destination_and_removes_staging(self):
        destination = self.run_dir / "02_etl"
        real_symlink = os.symlink

        def race_symlink(src, dst, **kwargs):
            destination.mkdir()
            return real_symlink(src, dst, **kwargs)

        with patch("greenfleet.pipeline.etl.fuelcast.os.symlink", side_effect=race_symlink):
            with self.assertRaises(FileExistsError):
                run_fuelcast_etl(self.run_dir)
        self.assertTrue(destination.is_dir())
        self.assertEqual(list(destination.iterdir()), [])
        self.assertEqual(list(self.run_dir.glob(".02_etl-data-*")), [])

    def test_snapshot_mutation_after_read_does_not_change_validated_rows(self):
        snapshot = self.source / "fuelcast_raw.csv"
        original = snapshot.read_bytes()
        real_read_bytes = Path.read_bytes

        def read_and_mutate(path):
            data = real_read_bytes(path)
            if path == snapshot:
                snapshot.write_bytes(data.replace(b"1.5", b"9.5"))
            return data

        with patch.object(Path, "read_bytes", read_and_mutate):
            result = run_fuelcast_etl(self.run_dir)
        audit = json.loads(result.audit_path.read_text())
        self.assertEqual(audit["source_snapshot_sha256"], hashlib.sha256(original).hexdigest())
        with result.canonical_path.open(newline="") as stream:
            self.assertEqual({row["fuel_consumption_kg_s"] for row in csv.DictReader(stream)}, {"1.5"})

    def test_manifest_schema_hash_count_and_column_failures(self):
        mutations = (
            lambda m: m.update(dataset_id="wrong"),
            lambda m: m.update(loaded_configurations=[EXPECTED_CONFIGS[0]]),
            lambda m: m.update(total_rows=99),
            lambda m: m["schema_fingerprints"].update({EXPECTED_CONFIGS[0]: "bad"}),
            lambda m: m.update(combined_schema_fingerprint="bad"),
            lambda m: m.update(snapshot_sha256="0" * 64),
            lambda m: m.update(raw_columns=list(reversed(RAW_COLUMNS))),
        )
        for mutate in mutations:
            self.write_source()
            mutate(self.manifest)
            self.write_manifest()
            with self.assertRaises(ValueError):
                run_fuelcast_etl(self.run_dir)
            self.assert_no_stage()
        self.write_source()
        self.manifest["row_counts"][EXPECTED_CONFIGS[0]] += 1
        self.manifest["total_rows"] += 1
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "row count mismatch"):
            run_fuelcast_etl(self.run_dir)
        self.assert_no_stage()


if __name__ == "__main__":
    unittest.main()
