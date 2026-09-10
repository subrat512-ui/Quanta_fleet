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
                "index": [1, 1, 2],
                "Consumer_Total_MomentaryFuel": [10.0, 10.0, None],
                "fuel_type": [" DM ", " DM ", None],
            }
        )

        cleaned, report = transform_dataframe(source)

        self.assertEqual(len(cleaned), 2)
        self.assertEqual(report.duplicates_removed, 1)
        self.assertEqual(int(cleaned.isna().sum().sum()), 0)
        self.assertEqual(cleaned.loc[0, "fuel_type"], "DM")
        self.assertEqual(cleaned.loc[1, "fuel_type"], "UNKNOWN")

    def test_validation_rejects_missing_required_column(self) -> None:
        with self.assertRaisesRegex(ValueError, "missing required columns"):
            validate_dataframe(pd.DataFrame({"index": [1]}))

    def test_run_etl_writes_clean_dataset_and_audit(self) -> None:
        source = pd.DataFrame(
            {
                "index": [1, 2],
                "Consumer_Total_MomentaryFuel": [2.0, None],
                "fuel_type": ["DM", None],
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_path = root / "raw.parquet"
            output_path = root / "clean.parquet"
            source.to_parquet(source_path, index=False)

            result = run_etl(source_path, output_path)

            self.assertTrue(result.dataset_path.is_file())
            self.assertTrue(result.audit_path.is_file())
            self.assertEqual(int(pd.read_parquet(output_path).isna().sum().sum()), 0)
            self.assertEqual(json.loads(result.audit_path.read_text())["output_rows"], 2)


if __name__ == "__main__":
    unittest.main()
