"""Dataset validation for the GreenFleet ETL pipeline."""

from dataclasses import asdict, dataclass
from typing import Iterable

import pandas as pd


RAW_REQUIRED_COLUMNS = (
    "Sailing speed",
    "Displacement",
    "Wind speed",
    "Fuel consumption rate",
    "vessel_type",
)
CANONICAL_REQUIRED_COLUMNS = (
    "record_id",
    "sailing_speed",
    "fuel_consumption_rate",
    "vessel_type",
)
DEFAULT_REQUIRED_COLUMNS = RAW_REQUIRED_COLUMNS


@dataclass(frozen=True)
class ValidationReport:
    row_count: int
    column_count: int
    duplicate_rows: int
    missing_by_column: dict[str, int]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def validate_dataframe(
    frame: pd.DataFrame,
    required_columns: Iterable[str] = DEFAULT_REQUIRED_COLUMNS,
) -> ValidationReport:
    """Validate required structure and return data-quality statistics."""
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("ETL input must be a pandas DataFrame")
    if frame.empty:
        raise ValueError("Dataset contains no rows")
    if frame.columns.has_duplicates:
        duplicates = frame.columns[frame.columns.duplicated()].unique().tolist()
        raise ValueError(f"Dataset has duplicate column names: {duplicates}")

    missing = sorted(set(required_columns).difference(frame.columns))
    if missing:
        raise ValueError(f"Dataset is missing required columns: {missing}")
    target_column = (
        "Fuel consumption rate"
        if "Fuel consumption rate" in frame.columns
        else "fuel_consumption_rate"
    )
    if target_column in frame.columns and not pd.api.types.is_numeric_dtype(frame[target_column]):
        raise TypeError(f"{target_column} must be numeric")

    null_counts = frame.isna().sum()
    return ValidationReport(
        row_count=len(frame),
        column_count=len(frame.columns),
        duplicate_rows=int(frame.duplicated().sum()),
        missing_by_column={column: int(count) for column, count in null_counts.items() if count},
    )
