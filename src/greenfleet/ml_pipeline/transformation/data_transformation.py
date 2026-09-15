import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from greenfleet.artifacts.data_transformation_artifact import (
    DataTransformationArtifact,
)

from greenfleet.config.data_transformation_config import (
    DataTransformationConfig,
)

from greenfleet.constants.training_pipeline_constants import (
    TARGET_COLUMN,
    NUMERICAL_FEATURE_COLUMNS,
    CATEGORICAL_FEATURE_COLUMNS,
    RANDOM_STATE,
    TRAIN_TEST_SPLIT_RATIO,
)

from greenfleet.logging.logger import logger


class DataTransformation:
    """
    Data transformation component.

    Responsibilities:
    1. Read validated data
    2. Separate input features and target
    3. Split data into train and test sets
    4. Impute missing values
    5. Scale numerical features
    6. Encode categorical features
    7. Save transformed datasets
    8. Save fitted preprocessor
    """

    def __init__(
        self,
        data_transformation_config: DataTransformationConfig,
    ) -> None:
        self.data_transformation_config = (
            data_transformation_config
        )

    @staticmethod
    def _save_numpy_data(
        file_path: Path,
        features: np.ndarray,
        target: np.ndarray,
    ) -> None:
        """
        Save transformed features and target in compressed NPZ format.
        """

        np.savez_compressed(
            file_path,
            features=features,
            target=target,
        )

    @staticmethod
    def _save_pickle(
        file_path: Path,
        object_to_save,
    ) -> None:
        """
        Save Python object using pickle.
        """

        with open(file_path, "wb") as file:
            pickle.dump(object_to_save, file)

    @staticmethod
    def _save_json(
        file_path: Path,
        data: dict | list,
    ) -> None:
        """
        Save dictionary or list as JSON.
        """

        with open(file_path, "w", encoding="utf-8") as file:
            json.dump(
                data,
                file,
                indent=4,
                default=str,
            )

    @staticmethod
    def _get_feature_names(
        preprocessor: ColumnTransformer,
    ) -> list[str]:
        """
        Get feature names after transformation.
        """

        feature_names = []

        for transformer_name, transformer, columns in (
            preprocessor.transformers_
        ):
            if transformer_name == "remainder":
                continue

            if transformer == "drop":
                continue

            if transformer == "passthrough":
                feature_names.extend(columns)
                continue

            fitted_pipeline = transformer

            if hasattr(
                fitted_pipeline,
                "get_feature_names_out",
            ):
                names = fitted_pipeline.get_feature_names_out(
                    columns
                )
                feature_names.extend(names.tolist())

        return feature_names

    def _get_preprocessor(self) -> ColumnTransformer:
        """
        Build preprocessing pipeline.

        Numerical:
        - Median imputation
        - Standard scaling

        Categorical:
        - Most-frequent imputation
        - One-hot encoding
        """

        numerical_pipeline = Pipeline(
            steps=[
                (
                    "imputer",
                    SimpleImputer(
                        strategy="median",
                    ),
                ),
                (
                    "scaler",
                    StandardScaler(),
                ),
            ]
        )

        categorical_pipeline = Pipeline(
            steps=[
                (
                    "imputer",
                    SimpleImputer(
                        strategy="most_frequent",
                    ),
                ),
                (
                    "encoder",
                    OneHotEncoder(
                        handle_unknown="ignore",
                        sparse_output=False,
                    ),
                ),
            ]
        )

        preprocessor = ColumnTransformer(
            transformers=[
                (
                    "numerical",
                    numerical_pipeline,
                    NUMERICAL_FEATURE_COLUMNS,
                ),
                (
                    "categorical",
                    categorical_pipeline,
                    CATEGORICAL_FEATURE_COLUMNS,
                ),
            ],
            remainder="drop",
        )

        return preprocessor

    def initiate_data_transformation(
        self,
        validated_data_file_path: Path,
    ) -> DataTransformationArtifact:
        """
        Execute the complete data transformation process.
        """

        logger.info(
            "Starting data transformation stage."
        )

        try:
            self.data_transformation_config.create_directories()

            logger.info(
                "Reading validated data from: %s",
                validated_data_file_path,
            )

            dataframe = pd.read_csv(
                validated_data_file_path
            )

            logger.info(
                "Validated data shape: %s",
                dataframe.shape,
            )

            required_columns = (
                NUMERICAL_FEATURE_COLUMNS
                + CATEGORICAL_FEATURE_COLUMNS
                + [TARGET_COLUMN]
            )

            missing_columns = [
                column
                for column in required_columns
                if column not in dataframe.columns
            ]

            if missing_columns:
                raise ValueError(
                    "Required columns are missing from validated "
                    f"dataset: {missing_columns}"
                )

            dataframe = dataframe[
                required_columns
            ].copy()

            dataframe = dataframe.dropna(
                subset=[TARGET_COLUMN]
            )

            dataframe[TARGET_COLUMN] = pd.to_numeric(
                dataframe[TARGET_COLUMN],
                errors="coerce",
            )

            dataframe = dataframe.dropna(
                subset=[TARGET_COLUMN]
            )

            if dataframe.empty:
                raise ValueError(
                    "No valid rows available after target cleaning."
                )

            features = dataframe.drop(
                columns=[TARGET_COLUMN]
            )

            target = dataframe[TARGET_COLUMN]

            logger.info(
                "Feature dataframe shape: %s",
                features.shape,
            )

            logger.info(
                "Target shape: %s",
                target.shape,
            )

            x_train, x_test, y_train, y_test = (
                train_test_split(
                    features,
                    target,
                    test_size=(
                        self.data_transformation_config.test_size
                    ),
                    random_state=(
                        self.data_transformation_config.random_state
                    ),
                )
            )

            logger.info(
                "Training data shape: %s",
                x_train.shape,
            )

            logger.info(
                "Testing data shape: %s",
                x_test.shape,
            )

            preprocessor = self._get_preprocessor()

            logger.info(
                "Fitting preprocessing pipeline on training data."
            )

            x_train_transformed = (
                preprocessor.fit_transform(x_train)
            )

            logger.info(
                "Transforming testing data."
            )

            x_test_transformed = (
                preprocessor.transform(x_test)
            )

            x_train_transformed = np.asarray(
                x_train_transformed,
                dtype=np.float32,
            )

            x_test_transformed = np.asarray(
                x_test_transformed,
                dtype=np.float32,
            )

            y_train_array = np.asarray(
                y_train,
                dtype=np.float32,
            )

            y_test_array = np.asarray(
                y_test,
                dtype=np.float32,
            )

            logger.info(
                "Transformed training shape: %s",
                x_train_transformed.shape,
            )

            logger.info(
                "Transformed testing shape: %s",
                x_test_transformed.shape,
            )

            self._save_numpy_data(
                file_path=(
                    self.data_transformation_config
                    .transformed_train_file_path
                ),
                features=x_train_transformed,
                target=y_train_array,
            )

            self._save_numpy_data(
                file_path=(
                    self.data_transformation_config
                    .transformed_test_file_path
                ),
                features=x_test_transformed,
                target=y_test_array,
            )

            self._save_pickle(
                file_path=(
                    self.data_transformation_config
                    .preprocessor_file_path
                ),
                object_to_save=preprocessor,
            )

            feature_names = self._get_feature_names(
                preprocessor
            )

            self._save_json(
                file_path=(
                    self.data_transformation_config
                    .feature_names_file_path
                ),
                data=feature_names,
            )

            transformation_report = {
                "input_shape": list(dataframe.shape),
                "feature_shape": list(features.shape),
                "train_shape": list(x_train.shape),
                "test_shape": list(x_test.shape),
                "transformed_train_shape": list(
                    x_train_transformed.shape
                ),
                "transformed_test_shape": list(
                    x_test_transformed.shape
                ),
                "target_column": TARGET_COLUMN,
                "numerical_features": (
                    NUMERICAL_FEATURE_COLUMNS
                ),
                "categorical_features": (
                    CATEGORICAL_FEATURE_COLUMNS
                ),
                "transformed_feature_count": len(
                    feature_names
                ),
                "test_size": (
                    self.data_transformation_config.test_size
                ),
                "random_state": (
                    self.data_transformation_config.random_state
                ),
            }

            self._save_json(
                file_path=(
                    self.data_transformation_config
                    .transformation_report_file_path
                ),
                data=transformation_report,
            )

            data_transformation_artifact = (
                DataTransformationArtifact(
                    transformed_train_file_path=(
                        self.data_transformation_config
                        .transformed_train_file_path
                    ),
                    transformed_test_file_path=(
                        self.data_transformation_config
                        .transformed_test_file_path
                    ),
                    preprocessor_file_path=(
                        self.data_transformation_config
                        .preprocessor_file_path
                    ),
                    feature_names_file_path=(
                        self.data_transformation_config
                        .feature_names_file_path
                    ),
                    transformation_report_file_path=(
                        self.data_transformation_config
                        .transformation_report_file_path
                    ),
                    train_shape=(
                        x_train_transformed.shape
                    ),
                    test_shape=(
                        x_test_transformed.shape
                    ),
                    numerical_feature_count=len(
                        NUMERICAL_FEATURE_COLUMNS
                    ),
                    categorical_feature_count=len(
                        CATEGORICAL_FEATURE_COLUMNS
                    ),
                    total_transformed_feature_count=len(
                        feature_names
                    ),
                    is_transformation_successful=True,
                )
            )

            logger.info(
                "Data transformation completed successfully."
            )

            logger.info(
                "Data transformation artifact: %s",
                data_transformation_artifact,
            )

            return data_transformation_artifact

        except Exception as exception:
            logger.exception(
                "Error occurred during data transformation."
            )

            raise exception