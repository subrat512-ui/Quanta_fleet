from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.ensemble import (
    GradientBoostingRegressor,
    RandomForestRegressor,
)
from sklearn.linear_model import LinearRegression
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)

from src.greenfleet.artifacts.model_trainer_artifact import (
    ModelTrainerArtifact,
)
from src.greenfleet.config.model_trainer_config import (
    ModelTrainerConfig,
)


class ModelTrainer:
    def __init__(
        self,
        model_trainer_config: ModelTrainerConfig,
    ):
        self.config = model_trainer_config

    def _load_data(self):
        train_data = np.load(
            self.config.transformed_train_file_path
        )

        test_data = np.load(
            self.config.transformed_test_file_path
        )

        X_train = train_data["features"]
        y_train = train_data["target"]

        X_test = test_data["features"]
        y_test = test_data["target"]

        return X_train, y_train, X_test, y_test

    def _get_models(self) -> dict[str, Any]:
        return {
            "LinearRegression": LinearRegression(),

            "RandomForestRegressor": RandomForestRegressor(
                n_estimators=200,
                random_state=42,
                n_jobs=-1,
            ),

            "GradientBoostingRegressor": GradientBoostingRegressor(
                n_estimators=200,
                learning_rate=0.05,
                max_depth=3,
                random_state=42,
            ),
        }

    def _evaluate_model(
        self,
        model,
        X_test,
        y_test,
    ) -> dict[str, float]:
        predictions = model.predict(X_test)

        mae = mean_absolute_error(
            y_test,
            predictions,
        )

        rmse = np.sqrt(
            mean_squared_error(
                y_test,
                predictions,
            )
        )

        r2 = r2_score(
            y_test,
            predictions,
        )

        return {
            "mae": float(mae),
            "rmse": float(rmse),
            "r2_score": float(r2),
        }

    def initiate_model_trainer(self) -> ModelTrainerArtifact:
        try:
            X_train, y_train, X_test, y_test = (
                self._load_data()
            )

            models = self._get_models()

            best_model = None
            best_model_name = None
            best_metrics = None

            print("\nStarting model training...")
            print(f"X_train shape: {X_train.shape}")
            print(f"y_train shape: {y_train.shape}")
            print(f"X_test shape: {X_test.shape}")
            print(f"y_test shape: {y_test.shape}")

            for model_name, model in models.items():
                print(f"\nTraining {model_name}...")

                model.fit(
                    X_train,
                    y_train,
                )

                metrics = self._evaluate_model(
                    model,
                    X_test,
                    y_test,
                )

                print(
                    f"MAE: {metrics['mae']:.4f}"
                )
                print(
                    f"RMSE: {metrics['rmse']:.4f}"
                )
                print(
                    f"R² Score: {metrics['r2_score']:.4f}"
                )

                if (
                    best_metrics is None
                    or metrics["r2_score"]
                    > best_metrics["r2_score"]
                ):
                    best_model = model
                    best_model_name = model_name
                    best_metrics = metrics

            model_path = (
                self.config.model_dir
                / "best_model.pkl"
            )

            joblib.dump(
                best_model,
                model_path,
            )

            print("\nBest model selected:")
            print(best_model_name)
            print(f"Saved at: {model_path}")

            return ModelTrainerArtifact(
                trained_model_file_path=model_path,
                model_name=best_model_name,
                mae=best_metrics["mae"],
                rmse=best_metrics["rmse"],
                r2_score=best_metrics["r2_score"],
                is_training_successful=True,
                message=(
                    "Model training completed successfully."
                ),
            )

        except Exception as error:
            return ModelTrainerArtifact(
                trained_model_file_path=Path(""),
                model_name="",
                mae=0.0,
                rmse=0.0,
                r2_score=0.0,
                is_training_successful=False,
                message=str(error),
            )