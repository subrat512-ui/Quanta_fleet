from pathlib import Path
from typing import Optional

from greenfleet.config.data_ingestion_config import (
    DataIngestionConfig,
)
from greenfleet.config.data_validation_config import (
    DataValidationConfig,
)
from greenfleet.config.data_transformation_config import (
    DataTransformationConfig,
)
from greenfleet.config.model_trainer_config import (
    ModelTrainerConfig,
)

from greenfleet.ml_pipeline.ingestion.data_ingestion import (
    DataIngestion,
)
from greenfleet.ml_pipeline.validation.data_validation import (
    DataValidation,
)
from greenfleet.ml_pipeline.transformation.data_transformation import (
    DataTransformation,
)
from greenfleet.ml_pipeline.training.model_trainer import (
    ModelTrainer,
)


class GreenFleetPipeline:
    """
    Complete GreenFleet ML pipeline.

    Flow:
        1. Data ingestion
        2. Data validation
        3. Data transformation
        4. Model training
    """

    def __init__(self):
        self.data_ingestion_config = DataIngestionConfig(
        pipeline_name="GreenFleet",
        pipeline_version="1.0",
        artifact_dir=Path("artifacts"),
        source_data_path=Path("data/raw"),
        ingested_data_path=Path("data/ingested"),
        metadata_file_path=Path("data/metadata.json"),)
        self.data_validation_config = DataValidationConfig()
        self.data_transformation_config = DataTransformationConfig()
        self.model_trainer_config = ModelTrainerConfig()

    def run_pipeline(self):
        print("\n" + "=" * 70)
        print("GREENFLEET ML PIPELINE STARTED")
        print("=" * 70)

        # ---------------------------------------------------------
        # 1. DATA INGESTION
        # ---------------------------------------------------------
        print("\n[1/4] Starting data ingestion...")

        data_ingestion = DataIngestion(
            data_ingestion_config=self.data_ingestion_config
        )

        data_ingestion_artifact = (
            data_ingestion.initiate_data_ingestion()
        )

        print("Data ingestion completed successfully.")
        print(
            f"Train data path: "
            f"{data_ingestion_artifact.trained_file_path}"
        )
        print(
            f"Test data path: "
            f"{data_ingestion_artifact.test_file_path}"
        )

        # ---------------------------------------------------------
        # 2. DATA VALIDATION
        # ---------------------------------------------------------
        print("\n[2/4] Starting data validation...")

        data_validation = DataValidation(
            data_validation_config=self.data_validation_config,
            data_ingestion_artifact=data_ingestion_artifact,
        )

        data_validation_artifact = (
            data_validation.initiate_data_validation()
        )

        if not data_validation_artifact.validation_status:
            raise RuntimeError(
                "Data validation failed. "
                "Check the validation report."
            )

        print("Data validation completed successfully.")

        # ---------------------------------------------------------
        # 3. DATA TRANSFORMATION
        # ---------------------------------------------------------
        print("\n[3/4] Starting data transformation...")

        data_transformation = DataTransformation(
            data_transformation_config=self.data_transformation_config,
            data_validation_artifact=data_validation_artifact,
        )

        data_transformation_artifact = (
            data_transformation.initiate_data_transformation()
        )

        print("Data transformation completed successfully.")
        print(
            "Transformed train path: "
            f"{data_transformation_artifact.transformed_train_file_path}"
        )
        print(
            "Transformed test path: "
            f"{data_transformation_artifact.transformed_test_file_path}"
        )
        print(
            "Preprocessor path: "
            f"{data_transformation_artifact.preprocessor_object_file_path}"
        )

        # ---------------------------------------------------------
        # 4. MODEL TRAINING
        # ---------------------------------------------------------
        print("\n[4/4] Starting model training...")

        model_trainer = ModelTrainer(
            model_trainer_config=self.model_trainer_config,
            data_transformation_artifact=data_transformation_artifact,
        )

        model_trainer_artifact = (
            model_trainer.initiate_model_trainer()
        )

        print("Model training completed successfully.")

        print(
            "Best model path: "
            f"{model_trainer_artifact.trained_model_file_path}"
        )

        print("\n" + "=" * 70)
        print("GREENFLEET ML PIPELINE COMPLETED SUCCESSFULLY")
        print("=" * 70)

        return model_trainer_artifact


def run_pipeline():
    """
    External function for running the complete pipeline.
    """
    pipeline = GreenFleetPipeline()
    return pipeline.run_pipeline()


if __name__ == "__main__":
    run_pipeline()