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

    def run_pipeline(self):
        """
        Execute all pipeline stages in sequence.
        """

        
        logger.info("Starting GreenFleet ML Pipeline")
        

        ingestion_artifact = self.run_data_ingestion()

        logger.info("Pipeline execution completed.")

        return ingestion_artifact


if __name__ == "__main__":
    pipeline = GreenFleetPipeline()

    pipeline.run_pipeline()