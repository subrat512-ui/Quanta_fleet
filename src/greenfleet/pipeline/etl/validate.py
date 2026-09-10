"""Dataset validation for the GreenFleet ETL pipeline."""

from dataclasses import asdict, dataclass
from typing import Iterable

import pandas as pd


DEFAULT_REQUIRED_COLUMNS = ("index", "Consumer_Total_MomentaryFuel")


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
    if not pd.api.types.is_numeric_dtype(frame["Consumer_Total_MomentaryFuel"]):
        raise TypeError("Consumer_Total_MomentaryFuel must be numeric")

    null_counts = frame.isna().sum()
    return ValidationReport(
        row_count=len(frame),
        column_count=len(frame.columns),
        duplicate_rows=int(frame.duplicated().sum()),
        missing_by_column={column: int(count) for column, count in null_counts.items() if count},
    )
