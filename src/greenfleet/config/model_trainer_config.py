from pathlib import Path

from greenfleet.constants.training_pipeline_constants import (
    TRANSFORMED_TRAIN_FILE,
    TRANSFORMED_TEST_FILE,
    MODEL_TRAINER_ARTIFACT_DIR,
)


class ModelTrainerConfig:
    """
    Configuration required for model training.
    """

    def __init__(
        self,
        transformed_train_file_path: Path = TRANSFORMED_TRAIN_FILE,
        transformed_test_file_path: Path = TRANSFORMED_TEST_FILE,
        model_dir: Path = MODEL_TRAINER_ARTIFACT_DIR,
    ):
        self.transformed_train_file_path = Path(
            transformed_train_file_path
        )

        self.transformed_test_file_path = Path(
            transformed_test_file_path
        )

        self.model_dir = Path(model_dir)

        self.model_dir.mkdir(
            parents=True,
            exist_ok=True,
        )