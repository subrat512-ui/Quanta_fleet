from dataclasses import dataclass
from pathlib import Path

from greenfleet.artifacts.base_artifact import BaseArtifact


@dataclass
class DataValidationArtifact(BaseArtifact):
    ingested_data_path: Path
    validation_report_path: Path

    validation_status: bool

    row_count: int
    column_count: int

    missing_value_count: int
    duplicate_row_count: int

    missing_columns: list[str]
    unexpected_columns: list[str]

    invalid_numeric_columns: list[str]
    validation_errors: list[str]
    validation_warnings: list[str]