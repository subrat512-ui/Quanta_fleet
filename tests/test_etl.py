import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from greenfleet.pipeline.etl.pipeline import run_etl
from greenfleet.pipeline.etl.transform import transform_dataframe
from greenfleet.pipeline.etl.validate import validate_dataframe


class ETLPipelineTests(unittest.TestCase):
    def test_transform_removes_duplicates_and_imputes_values(self) -> None:
        source = pd.DataFrame(
            {
                "Sailing speed": [10.0, 10.0, 12.0],
                "Displacement": [20.0, 20.0, 21.0],
                "Wind speed": [3.0, 3.0, 4.0],
                "Fuel consumption rate": [10.0, 10.0, None],
                "vessel_type": [" Tanker ", " Tanker ", None],
            }
        )

        cleaned, report = transform_dataframe(source)

        self.assertEqual(len(cleaned), 2)
        self.assertEqual(report.duplicates_removed, 1)
        self.assertEqual(int(cleaned.isna().sum().sum()), 0)
        self.assertIn("record_id", cleaned.columns)
        self.assertEqual(cleaned.loc[0, "vessel_type"], "Tanker")
        self.assertEqual(cleaned.loc[1, "vessel_type"], "UNKNOWN")

    def test_validation_rejects_missing_required_column(self) -> None:
        with self.assertRaisesRegex(ValueError, "missing required columns"):
            validate_dataframe(pd.DataFrame({"Sailing speed": [1]}))

    def test_new_schema_is_normalized_and_keeps_missing_timestamp(self) -> None:
        source = pd.DataFrame(
            {
                "Sailing speed": [10.0],
                "Displacement": [20.0],
                "Wind speed": [3.0],
                "Fuel consumption rate": [2.0],
                "vessel_type": ["Tanker"],
                "Current GMT Dttm": [None],
                "Swell height": [None],
            }
        )

        cleaned, _ = transform_dataframe(source)

        self.assertIn("sailing_speed", cleaned.columns)
        self.assertIn("swell_height_was_missing", cleaned.columns)
        self.assertTrue(pd.isna(cleaned.loc[0, "observation_timestamp"]))
        self.assertEqual(cleaned.loc[0, "swell_height"], 0.0)

    def test_run_etl_writes_clean_dataset_and_audit(self) -> None:
        source = pd.DataFrame(
            {
                "Sailing speed": [10.0, 12.0],
                "Displacement": [20.0, 21.0],
                "Wind speed": [3.0, 4.0],
                "Fuel consumption rate": [2.0, None],
                "vessel_type": ["Tanker", None],
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_path = root / "raw.csv"
            output_path = root / "clean.csv"
            source.to_csv(source_path, index=False)

            result = run_etl(source_path, output_path)

            self.assertTrue(result.dataset_path.is_file())
            self.assertTrue(result.audit_path.is_file())
            self.assertEqual(int(pd.read_csv(output_path).isna().sum().sum()), 0)
            self.assertEqual(json.loads(result.audit_path.read_text())["output_rows"], 2)


if __name__ == "__main__":
    unittest.main()
