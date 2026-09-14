from dataclasses import dataclass
from pathlib import Path

from greenfleet.config.base_config import BaseConfig


@dataclass
class DataIngestionConfig(BaseConfig):
    """
    Configuration required for data ingestion.
    """

    source_data_path: Path

    ingested_data_path: Path

    metadata_file_path: Path