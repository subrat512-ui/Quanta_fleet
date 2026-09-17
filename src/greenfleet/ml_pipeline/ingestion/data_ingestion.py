import json
import shutil

import pandas as pd

from greenfleet.artifacts.data_ingestion_artifact import DataIngestionArtifact
from greenfleet.config.data_ingestion_config import DataIngestionConfig
from greenfleet.logging.logger import logger


class DataIngestion:
    def __init__(self, config: DataIngestionConfig):
        self.config = config

    def initiate_data_ingestion(self) -> DataIngestionArtifact:
        logger.info("Starting data ingestion...")

        self.config.create_directories()

        source_path = self.config.source_data_path
        ingested_path = self.config.ingested_data_path
        metadata_path = self.config.metadata_file_path

        if not source_path.exists():
            raise FileNotFoundError(
                f"Source data file not found: {source_path}"
            )

        # Copy original CSV into artifacts folder
        shutil.copy2(source_path, ingested_path)

        # Read copied dataset
        dataframe = pd.read_csv(ingested_path)

        # Create metadata
        metadata = {
            "source_data_path": str(source_path),
            "ingested_data_path": str(ingested_path),
            "row_count": int(dataframe.shape[0]),
            "column_count": int(dataframe.shape[1]),
            "column_names": dataframe.columns.tolist(),
        }

        with open(metadata_path, "w", encoding="utf-8") as file:
            json.dump(metadata, file, indent=4)

        print(f"Rows: {dataframe.shape[0]}")
        print(f"Columns: {dataframe.shape[1]}")
        print(f"Ingested file: {ingested_path}")

        return DataIngestionArtifact(
            artifact_name="data_ingestion_artifact",
            artifact_dir=self.config.artifact_dir,
            source_data_path=source_path,
            ingested_data_path=ingested_path,
            metadata_file_path=metadata_path,
            row_count=int(dataframe.shape[0]),
            column_count=int(dataframe.shape[1]),
            column_names=dataframe.columns.tolist(),
        )