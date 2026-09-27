"""Repository foundation checks that do not require FuelCast or MongoDB."""

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path

from greenfleet.artifacts.data_transformation_artifact import DataTransformationArtifact
from greenfleet.artifacts.data_validation_artifact import DataValidationArtifact
from greenfleet.artifacts.model_trainer_artifact import ModelTrainerArtifact
from greenfleet.constants import training_pipeline_constants as constants
from greenfleet.ml_pipeline.pipeline import GreenFleetPipeline


class FoundationTests(unittest.TestCase):
    def test_source_artifacts_are_importable(self):
        self.assertEqual(DataTransformationArtifact.__name__, "DataTransformationArtifact")
        self.assertEqual(DataValidationArtifact.__name__, "DataValidationArtifact")
        self.assertEqual(ModelTrainerArtifact.__name__, "ModelTrainerArtifact")

    def test_paths_and_constants_resolve_from_repository_root(self):
        repository_root = Path(__file__).resolve().parents[1]
        self.assertEqual(constants.PROJECT_ROOT, repository_root)
        self.assertEqual(constants.ARTIFACTS_DIR, repository_root / "artifacts")
        self.assertEqual(
            constants.TRANSFORMED_TRAIN_FILE,
            constants.ARTIFACTS_DIR
            / constants.DATA_TRANSFORMATION_DIR_NAME
            / constants.DATA_TRANSFORMATION_TRANSFORMED_DATA_DIR
            / constants.DATA_TRANSFORMATION_TRANSFORMED_TRAIN_FILE_NAME,
        )
        self.assertEqual(
            constants.TRANSFORMED_TEST_FILE,
            constants.ARTIFACTS_DIR
            / constants.DATA_TRANSFORMATION_DIR_NAME
            / constants.DATA_TRANSFORMATION_TRANSFORMED_DATA_DIR
            / constants.DATA_TRANSFORMATION_TRANSFORMED_TEST_FILE_NAME,
        )

    def test_single_pipeline_module_and_help(self):
        self.assertIsNone(importlib.util.find_spec("greenfleet.ml_pipeline.pipeline2"))
        self.assertTrue(hasattr(GreenFleetPipeline, "run_pipeline"))
        result = subprocess.run(
            [sys.executable, "-m", "greenfleet.ml_pipeline.pipeline", "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("FuelCast support is pending", result.stdout)


if __name__ == "__main__":
    unittest.main()
