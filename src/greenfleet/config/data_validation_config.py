from dataclasses import dataclass, field
from pathlib import Path

from greenfleet.config.base_config import BaseConfig
from greenfleet.constants.training_pipeline_constants import (
    INGESTED_DATA_FILE,
    VALIDATION_REPORT_FILE,
    REQUIRED_COLUMNS,
)


@dataclass
class DataValidationConfig(BaseConfig):
    """
    Configuration required for data validation.
    """

    ingested_data_path: Path = INGESTED_DATA_FILE

    validation_report_path: Path = VALIDATION_REPORT_FILE

    required_columns: list[str] = field(
        default_factory=lambda: list(REQUIRED_COLUMNS)
    )

    max_missing_percentage: float = 5.0

    allow_duplicates: bool = False