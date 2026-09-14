"""Cleaning and feature-safe transformations for vessel telemetry."""

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd


COLUMN_RENAMES = {
    "Sailing speed": "sailing_speed",
    "Displacement": "displacement",
    "Trim": "trim",
    "Wind speed": "wind_speed",
    "Wind direction (Rel.)": "wind_direction_relative",
    "Combined wave height": "combined_wave_height",
    "Combined Wave period": "combined_wave_period",
    "Combined wave direction (Rel.)": "combined_wave_direction_relative",
    "Sea current speed": "sea_current_speed",
    "Sea current direction (Rel.)": "sea_current_direction_relative",
    "Sea water temperature": "sea_water_temperature",
    "Fuel consumption rate": "fuel_consumption_rate",
    "Current GMT Dttm": "observation_timestamp",
    "Swell height": "swell_height",
    "Swell direction (Rel.)": "swell_direction_relative",
    "Wind wave height": "wind_wave_height",
    "Wind wave direction (Rel.)": "wind_wave_direction_relative",
}
NUMERIC_FEATURE_COLUMNS = frozenset(COLUMN_RENAMES.values()) - {"observation_timestamp"}


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
    result = result.rename(columns=COLUMN_RENAMES)
    result = result.replace([np.inf, -np.inf], np.nan)

    # A completely empty CSV measurement column may be inferred as a string;
    # its domain name still identifies it as a numeric operational feature.
    for column in NUMERIC_FEATURE_COLUMNS.intersection(result.columns):
        result[column] = pd.to_numeric(result[column], errors="coerce")

    if "observation_timestamp" in result.columns:
        result["observation_timestamp"] = pd.to_datetime(
            result["observation_timestamp"], errors="coerce", format="mixed", utc=True
        )

    before_deduplication = len(result)
    result = result.drop_duplicates().reset_index(drop=True)
    numeric_columns = result.select_dtypes(include=[np.number]).columns
    categorical_columns = result.select_dtypes(include=["object", "string", "category"]).columns

    # Retain information about source-specific telemetry gaps before filling
    # them.  For example, swell data exists only for a subset of this source.
    numeric_missing = int(result[numeric_columns].isna().sum().sum())
    for column in numeric_columns:
        if result[column].isna().any():
            result[f"{column}_was_missing"] = result[column].isna().astype("int8")
    for column in numeric_columns:
        if result[column].isna().any():
            median = result[column].median()
            result[column] = result[column].fillna(0.0 if pd.isna(median) else median)

    categorical_missing = int(result[categorical_columns].isna().sum().sum())
    for column in categorical_columns:
        normalized = result[column].astype("string").str.strip()
        result[column] = normalized.mask(normalized.isna() | normalized.eq(""), "UNKNOWN")

    # Stable across reruns with identical rows and suitable for MongoDB upserts.
    hashes = pd.util.hash_pandas_object(result, index=False).astype("uint64")
    result.insert(0, "record_id", hashes.map(lambda value: f"{int(value):016x}"))

    report = TransformationReport(
        input_rows=len(frame),
        output_rows=len(result),
        duplicates_removed=before_deduplication - len(result),
        numeric_values_imputed=numeric_missing,
        categorical_values_imputed=categorical_missing,
    )
    return result, report
