from dataclasses import dataclass
from pathlib import Path

from greenfleet.constants.training_pipeline_constants import (
    ARTIFACTS_DIR,
    DATA_TRANSFORMATION_DIR_NAME,
    DATA_TRANSFORMATION_TRANSFORMED_DATA_DIR,
    DATA_TRANSFORMATION_TRANSFORMED_TRAIN_FILE_NAME,
    DATA_TRANSFORMATION_TRANSFORMED_TEST_FILE_NAME,
    DATA_TRANSFORMATION_PREPROCESSOR_FILE_NAME,
    DATA_TRANSFORMATION_FEATURE_NAMES_FILE_NAME,
    DATA_TRANSFORMATION_REPORT_FILE_NAME,
)


@dataclass
class DataTransformationConfig:
    """
    Configuration class for the data transformation component.
    """

    data_transformation_dir: Path = (
        ARTIFACTS_DIR / DATA_TRANSFORMATION_DIR_NAME
    )

    transformed_data_dir: Path = (
        ARTIFACTS_DIR
        / DATA_TRANSFORMATION_DIR_NAME
        / DATA_TRANSFORMATION_TRANSFORMED_DATA_DIR
    )

    transformed_train_file_path: Path = (
        ARTIFACTS_DIR
        / DATA_TRANSFORMATION_DIR_NAME
        / DATA_TRANSFORMATION_TRANSFORMED_DATA_DIR
        / DATA_TRANSFORMATION_TRANSFORMED_TRAIN_FILE_NAME
    )

    transformed_test_file_path: Path = (
        ARTIFACTS_DIR
        / DATA_TRANSFORMATION_DIR_NAME
        / DATA_TRANSFORMATION_TRANSFORMED_DATA_DIR
        / DATA_TRANSFORMATION_TRANSFORMED_TEST_FILE_NAME
    )

    preprocessor_file_path: Path = (
        ARTIFACTS_DIR
        / DATA_TRANSFORMATION_DIR_NAME
        / DATA_TRANSFORMATION_PREPROCESSOR_FILE_NAME
    )

    feature_names_file_path: Path = (
        ARTIFACTS_DIR
        / DATA_TRANSFORMATION_DIR_NAME
        / DATA_TRANSFORMATION_FEATURE_NAMES_FILE_NAME
    )

    transformation_report_file_path: Path = (
        ARTIFACTS_DIR
        / DATA_TRANSFORMATION_DIR_NAME
        / DATA_TRANSFORMATION_REPORT_FILE_NAME
    )

    test_size: float = 0.2

    random_state: int = 42

    numerical_imputer_strategy: str = "median"

    categorical_imputer_strategy: str = "most_frequent"

    scaler_type: str = "standard"

    handle_unknown_categories: str = "ignore"

    sparse_output: bool = False

    def create_directories(self) -> None:
        """
        Create all directories required by the transformation component.
        """

        self.data_transformation_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.transformed_data_dir.mkdir(
            parents=True,
            exist_ok=True,
        )