"""Prediction utilities for the trained GreenFleet fuel model.

This module is intentionally independent of FastAPI.  A route handler can
instantiate :class:`FuelConsumptionPredictor` once at application startup and
call ``predict`` for each request.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import joblib
import pandas as pd

from greenfleet.constants.training_pipeline_constants import (
    CATEGORICAL_FEATURE_COLUMNS,
    MODEL_TRAINER_ARTIFACT_DIR,
    NUMERICAL_FEATURE_COLUMNS,
    DATA_TRANSFORMATION_DIR_NAME,
    DATA_TRANSFORMATION_PREPROCESSOR_FILE_NAME,
)


FEATURE_COLUMNS = (
    NUMERICAL_FEATURE_COLUMNS + CATEGORICAL_FEATURE_COLUMNS
)

DEFAULT_PREPROCESSOR_PATH = (
    MODEL_TRAINER_ARTIFACT_DIR.parent
    / DATA_TRANSFORMATION_DIR_NAME
    / DATA_TRANSFORMATION_PREPROCESSOR_FILE_NAME
)

DEFAULT_MODEL_PATH = MODEL_TRAINER_ARTIFACT_DIR / "best_model.pkl"


class FuelConsumptionPredictor:
    """Load the persisted preprocessing pipeline and trained model."""

    def __init__(
        self,
        model_path: Path = DEFAULT_MODEL_PATH,
        preprocessor_path: Path = DEFAULT_PREPROCESSOR_PATH,
    ) -> None:
        self.model_path = Path(model_path)
        self.preprocessor_path = Path(preprocessor_path)

        if not self.model_path.is_file():
            raise FileNotFoundError(
                f"Trained model was not found: {self.model_path}"
            )

        if not self.preprocessor_path.is_file():
            raise FileNotFoundError(
                f"Preprocessor was not found: {self.preprocessor_path}"
            )

        self.model = joblib.load(self.model_path)
        self.preprocessor = joblib.load(self.preprocessor_path)

    @staticmethod
    def _to_dataframe(
        features: Mapping[str, Any] | pd.DataFrame,
    ) -> pd.DataFrame:
        """Convert one prediction request into the training input schema."""

        if isinstance(features, pd.DataFrame):
            dataframe = features.copy()
        elif isinstance(features, Mapping):
            dataframe = pd.DataFrame([dict(features)])
        else:
            raise TypeError(
                "Prediction input must be a mapping or pandas DataFrame."
            )

        missing_columns = [
            column
            for column in FEATURE_COLUMNS
            if column not in dataframe.columns
        ]
        if missing_columns:
            raise ValueError(
                "Missing required prediction fields: "
                f"{missing_columns}"
            )

        if dataframe.empty:
            raise ValueError("Prediction input must contain at least one row.")

        # Select only the columns used during training and preserve their
        # ordering. This also makes the method safe for FastAPI payloads that
        # contain request metadata or other unrelated fields.
        return dataframe.loc[:, FEATURE_COLUMNS]

    def predict(
        self,
        features: Mapping[str, Any] | pd.DataFrame,
    ) -> float | list[float]:
        """Return fuel-consumption predictions for one or more input rows."""

        dataframe = self._to_dataframe(features)
        transformed_features = self.preprocessor.transform(dataframe)
        predictions = self.model.predict(transformed_features)
        values = [float(value) for value in predictions]

        if len(values) == 1:
            return values[0]
        return values


def predict_fuel_consumption(
    features: Mapping[str, Any] | pd.DataFrame,
    model_path: Path = DEFAULT_MODEL_PATH,
    preprocessor_path: Path = DEFAULT_PREPROCESSOR_PATH,
) -> float | list[float]:
    """Load artifacts and predict fuel consumption in one call."""

    predictor = FuelConsumptionPredictor(
        model_path=model_path,
        preprocessor_path=preprocessor_path,
    )
    return predictor.predict(features)

