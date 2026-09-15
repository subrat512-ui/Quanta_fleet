
from pathlib import Path
from greenfleet.constants.training_pipeline_constants import (
    DATA_INGESTION_ARTIFACT_DIR,
    DATA_VALIDATION_ARTIFACT_DIR,
    INGESTED_DATA_FILE,
    INGESTION_METADATA_FILE,
    VALIDATION_REPORT_FILE,
    PIPELINE_NAME,
    PIPELINE_VERSION,
    SOURCE_DATA_FILE,
)

from greenfleet.config.data_ingestion_config import (
    DataIngestionConfig,
)

from greenfleet.config.data_validation_config import (
    DataValidationConfig,
)

from greenfleet.config.data_transformation_config import (
    DataTransformationConfig,
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

from greenfleet.logging.logger import logger


class GreenFleetPipeline:
    """
    Main pipeline class responsible for executing
    different stages of the GreenFleet ML pipeline.

    Pipeline flow:

    Data Ingestion
        ↓
    Data Validation
        ↓
    Data Transformation
    """

    def __init__(self):
        """
        Initialize all pipeline configurations.
        """

        self.ingestion_config = DataIngestionConfig(
            pipeline_name=PIPELINE_NAME,
            pipeline_version=PIPELINE_VERSION,
            artifact_dir=DATA_INGESTION_ARTIFACT_DIR,
            source_data_path=SOURCE_DATA_FILE,
            ingested_data_path=INGESTED_DATA_FILE,
            metadata_file_path=INGESTION_METADATA_FILE,
        )

        self.validation_config = DataValidationConfig(
            pipeline_name=PIPELINE_NAME,
            pipeline_version=PIPELINE_VERSION,
            artifact_dir=DATA_VALIDATION_ARTIFACT_DIR,
            ingested_data_path=INGESTED_DATA_FILE,
            validation_report_path=VALIDATION_REPORT_FILE,
            required_columns=[
                "record_id",
                "sailing_speed",
                "displacement",
                "trim",
                "wind_speed",
                "wind_direction_relative",
                "combined_wave_height",
                "combined_wave_period",
                "combined_wave_direction_relative",
                "sea_current_speed",
                "sea_current_direction_relative",
                "sea_water_temperature",
                "fuel_consumption_rate",
                "data_source",
                "observation_timestamp",
                "swell_height",
                "swell_direction_relative",
                "wind_wave_height",
                "wind_wave_direction_relative",
                "vessel_type",
                "vessel_type_source",
                "combined_wave_period_was_missing",
                "swell_height_was_missing",
                "swell_direction_relative_was_missing",
                "wind_wave_height_was_missing",
                "wind_wave_direction_relative_was_missing",
            ],
            max_missing_percentage=5.0,
            allow_duplicates=False,
        )

        self.data_transformation_config = (
            DataTransformationConfig()
        )

    def run_data_ingestion(self):
        """
        Execute the data ingestion stage.
        """

        logger.info(
            "Starting data ingestion stage..."
        )

        data_ingestion = DataIngestion(
            config=self.ingestion_config
        )

        data_ingestion_artifact = (
            data_ingestion.initiate_data_ingestion()
        )

        logger.info(
            "Data ingestion stage completed."
        )

        logger.info(
            "Data Ingestion Artifact: %s",
            data_ingestion_artifact,
        )

        if hasattr(
            data_ingestion_artifact,
            "to_dict",
        ):
            logger.info(
                data_ingestion_artifact.to_dict()
            )

        return data_ingestion_artifact

    def run_data_validation(
        self,
        data_ingestion_artifact=None,
    ):
        """
        Execute the data validation stage.

        The ingestion artifact is accepted for pipeline
        compatibility. The validation component reads
        the configured ingested data path.
        """

        logger.info(
            "Starting data validation stage..."
        )

        data_validation = DataValidation(
            config=self.validation_config
        )

        data_validation_artifact = (
            data_validation.initiate_data_validation()
        )

        logger.info(
            "Data validation stage completed "
            "with status: %s",
            data_validation_artifact.validation_status,
        )

        logger.info(
            "Data Validation Artifact: %s",
            data_validation_artifact,
        )

        return data_validation_artifact

    def start_data_transformation(
        self,
        data_validation_artifact,
    ):
        """
        Execute the data transformation stage.
        """

        logger.info(
            "Starting data transformation stage..."
        )

        if not data_validation_artifact.validation_status:
            raise ValueError(
                "Data validation failed. "
                "Data transformation cannot continue."
            )

        validated_data_file_path = (
            self._get_validated_data_file_path(
                data_validation_artifact
            )
        )

        logger.info(
            "Validated data path: %s",
            validated_data_file_path,
        )

        data_transformation = DataTransformation(
            data_transformation_config=(
                self.data_transformation_config
            )
        )

        data_transformation_artifact = (
            data_transformation.initiate_data_transformation(
                validated_data_file_path=(
                    validated_data_file_path
                )
            )
        )

        logger.info(
            "Data transformation stage completed."
        )

        logger.info(
            "Data Transformation Artifact: %s",
            data_transformation_artifact,
        )

        return data_transformation_artifact

    def _get_validated_data_file_path(self, data_validation_artifact):
        """
        Return the dataset path to be used by data transformation.

        The current validation stage validates the ingested dataset directly,
        so ingested_data_path is used as the validated dataset path.
        """

        possible_attributes = [
            "validated_data_file_path",
            "valid_data_file_path",
            "validated_data_path",
            "valid_data_path",
            "ingested_data_path",
        ]

        for attribute in possible_attributes:
            if hasattr(data_validation_artifact, attribute):
                file_path = getattr(data_validation_artifact, attribute)

                if file_path is not None:
                    file_path = Path(file_path)

                    if file_path.exists():
                        logger.info(
                            f"Using validated data file: {file_path}"
                        )
                        return file_path

        raise AttributeError(
            "Could not find a valid dataset path inside "
            f"DataValidationArtifact. Expected one of: {possible_attributes}"
        )

    def run_pipeline(self):
        """
        Run the complete GreenFleet training pipeline.
        """

        logger.info(
            "========== TRAINING PIPELINE STARTED =========="
        )

        # ----------------------------------------------------
        # Stage 1: Data Ingestion
        # ----------------------------------------------------

        data_ingestion_artifact = (
            self.run_data_ingestion()
        )

        # ----------------------------------------------------
        # Stage 2: Data Validation
        # ----------------------------------------------------

        data_validation_artifact = (
            self.run_data_validation(
                data_ingestion_artifact=(
                    data_ingestion_artifact
                )
            )
        )

        if not data_validation_artifact.validation_status:
            logger.error(
                "Data validation failed."
            )

            raise ValueError(
                "Data validation failed. "
                "Training pipeline stopped."
            )

        # ----------------------------------------------------
        # Stage 3: Data Transformation
        # ----------------------------------------------------

        data_transformation_artifact = (
            self.start_data_transformation(
                data_validation_artifact=(
                    data_validation_artifact
                )
            )
        )

        logger.info(
            "Data transformation artifact received: %s",
            data_transformation_artifact,
        )

        logger.info(
            "========== TRAINING PIPELINE COMPLETED =========="
        )

        return data_transformation_artifact


if __name__ == "__main__":
    pipeline = GreenFleetPipeline()

    pipeline.run_pipeline()