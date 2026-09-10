"""Cleaning and feature-safe transformations for vessel telemetry."""

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class TransformationReport:
    input_rows: int
    output_rows: int
    duplicates_removed: int
    numeric_values_imputed: int
    categorical_values_imputed: int

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


def transform_dataframe(frame: pd.DataFrame) -> tuple[pd.DataFrame, TransformationReport]:
    """Clean telemetry without dropping valid sparse observations.

    Numeric sensor gaps receive the column median; categorical gaps become
    ``UNKNOWN``. Exact duplicate records are removed.
    """
    result = frame.copy()
    result.columns = [str(column).strip() for column in result.columns]
    result = result.replace([np.inf, -np.inf], np.nan)

    before_deduplication = len(result)
    result = result.drop_duplicates().reset_index(drop=True)
    numeric_columns = result.select_dtypes(include=[np.number]).columns
    categorical_columns = result.select_dtypes(include=["object", "string", "category"]).columns

    numeric_missing = int(result[numeric_columns].isna().sum().sum())
    for column in numeric_columns:
        if result[column].isna().any():
            median = result[column].median()
            result[column] = result[column].fillna(0.0 if pd.isna(median) else median)

    categorical_missing = int(result[categorical_columns].isna().sum().sum())
    for column in categorical_columns:
        normalized = result[column].astype("string").str.strip()
        result[column] = normalized.mask(normalized.isna() | normalized.eq(""), "UNKNOWN")

    report = TransformationReport(
        input_rows=len(frame),
        output_rows=len(result),
        duplicates_removed=before_deduplication - len(result),
        numeric_values_imputed=numeric_missing,
        categorical_values_imputed=categorical_missing,
    )
    return result, report
