from dataclasses import dataclass
from pathlib import Path

from greenfleet.config.base_config import BaseConfig
from greenfleet.constants.training_pipeline_constants import (
    SOURCE_DATA_FILE,
    INGESTED_DATA_FILE,
    INGESTION_METADATA_FILE,
)


@dataclass
class DataIngestionConfig(BaseConfig):
    """
    Configuration required for data ingestion.
    """

    source_data_path: Path = SOURCE_DATA_FILE
    ingested_data_path: Path = INGESTED_DATA_FILE
    metadata_file_path: Path = INGESTION_METADATA_FILE