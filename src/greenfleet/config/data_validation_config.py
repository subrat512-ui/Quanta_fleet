from dataclasses import dataclass
from pathlib import Path

from greenfleet.config.base_config import BaseConfig


@dataclass
class DataValidationConfig(BaseConfig):
    ingested_data_path: Path
    validation_report_path: Path

    required_columns: list[str]

    max_missing_percentage: float = 5.0
    allow_duplicates: bool = False