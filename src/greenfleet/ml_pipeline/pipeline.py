from greenfleet.constants.training_pipeline_constants import (
    DATA_VALIDATION_ARTIFACT_DIR,
    INGESTED_DATA_FILE,
    VALIDATION_REPORT_FILE,
)
from greenfleet.config.data_validation_config import (
    DataValidationConfig,
)
from greenfleet.ml_pipeline.validation.data_validation import (
    DataValidation,
)






from greenfleet.logging.logger import logger


from greenfleet.constants.training_pipeline_constants import (
    DATA_INGESTION_ARTIFACT_DIR,
    INGESTED_DATA_FILE,
    INGESTION_METADATA_FILE,
    PIPELINE_NAME,
    PIPELINE_VERSION,
    SOURCE_DATA_FILE,
)

from greenfleet.config.data_ingestion_config import (
    DataIngestionConfig,
)

from greenfleet.ml_pipeline.ingestion.data_ingestion import (
    DataIngestion,
)


class GreenFleetPipeline:
    """
    Main pipeline class responsible for executing
    different stages of the GreenFleet ML pipeline.
    """

    def __init__(self):
        """
        Initialize the pipeline.
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

    def run_data_ingestion(self):
        """
        Execute the data ingestion stage.
        """

        logger.info("Starting data ingestion stage...")

        data_ingestion = DataIngestion(
            config=self.ingestion_config
        )

        data_ingestion_artifact = (
            data_ingestion.initiate_data_ingestion()
        )

        logger.info("Data ingestion stage completed.")

        logger.info("Data Ingestion Artifact:")
        logger.info(data_ingestion_artifact.to_dict())

        return data_ingestion_artifact


    def run_data_validation(self):
        logger.info("Starting data validation stage")

        data_validation = DataValidation(
            config=self.validation_config
        )

        data_validation_artifact = (
            data_validation.initiate_data_validation()
        )

        logger.info(
            "Data validation stage completed with status: %s",
            data_validation_artifact.validation_status,
        )

        return data_validation_artifact


    def run_pipeline(self):
        logger.info("=" * 60)
        logger.info("Starting GreenFleet ML Pipeline")
        logger.info("=" * 60)

        ingestion_artifact = self.run_data_ingestion()

        if not ingestion_artifact.status:
            logger.error(
                "Pipeline stopped because data ingestion failed"
            )
            return ingestion_artifact

        validation_artifact = self.run_data_validation()

        if not validation_artifact.validation_status:
            logger.error(
                "Pipeline stopped because data validation failed"
            )
            return validation_artifact

        logger.info(
            "GreenFleet ML Pipeline completed successfully"
        )

        return validation_artifact


if __name__ == "__main__":
    pipeline = GreenFleetPipeline()

    pipeline.run_pipeline()