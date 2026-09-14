import json
from pathlib import Path

import pandas as pd

from greenfleet.artifacts.data_validation_artifact import (
    DataValidationArtifact,
)
from greenfleet.config.data_validation_config import DataValidationConfig
from greenfleet.logging.logger import logger

class DataValidation:
    def __init__(self, config: DataValidationConfig):
        self.config = config

    def initiate_data_validation(self) -> DataValidationArtifact:
        logger.info("Starting data validation stage")

        self.config.create_directories()

        ingested_data_path = self.config.ingested_data_path
        validation_report_path = self.config.validation_report_path

        validation_errors: list[str] = []
        validation_warnings: list[str] = []

        missing_columns: list[str] = []
        unexpected_columns: list[str] = []
        invalid_numeric_columns: list[str] = []

        row_count = 0
        column_count = 0
        missing_value_count = 0
        duplicate_row_count = 0

        # ---------------------------------------------------------
        # 1. Check whether ingested file exists
        # ---------------------------------------------------------
        if not ingested_data_path.exists():
            error_message = (
                f"Ingested data file not found: {ingested_data_path}"
            )

            logger.error(error_message)
            validation_errors.append(error_message)

            validation_report = {
                "validation_status": False,
                "errors": validation_errors,
                "warnings": validation_warnings,
            }

            with open(
                validation_report_path,
                "w",
                encoding="utf-8",
            ) as file:
                json.dump(validation_report, file, indent=4)

            return DataValidationArtifact(
                artifact_name="data_validation_artifact",
                artifact_dir=self.config.artifact_dir,
                status=False,
                message="Data validation failed because input file was missing",
                ingested_data_path=ingested_data_path,
                validation_report_path=validation_report_path,
                validation_status=False,
                row_count=0,
                column_count=0,
                missing_value_count=0,
                duplicate_row_count=0,
                missing_columns=[],
                unexpected_columns=[],
                invalid_numeric_columns=[],
                validation_errors=validation_errors,
                validation_warnings=validation_warnings,
            )

        # ---------------------------------------------------------
        # 2. Load dataset
        # ---------------------------------------------------------
        logger.info(
            "Loading ingested dataset from: %s",
            ingested_data_path,
        )

        dataframe = pd.read_csv(ingested_data_path)

        row_count = int(dataframe.shape[0])
        column_count = int(dataframe.shape[1])

        logger.info(
            "Dataset loaded successfully: rows=%s, columns=%s",
            row_count,
            column_count,
        )

        # ---------------------------------------------------------
        # 3. Check empty dataset
        # ---------------------------------------------------------
        if dataframe.empty:
            error_message = "Dataset is empty"

            logger.error(error_message)
            validation_errors.append(error_message)

        # ---------------------------------------------------------
        # 4. Check required columns
        # ---------------------------------------------------------
        actual_columns = set(dataframe.columns)
        required_columns = set(self.config.required_columns)

        missing_columns = sorted(
            required_columns - actual_columns
        )

        unexpected_columns = sorted(
            actual_columns - required_columns
        )

        if missing_columns:
            error_message = (
                f"Required columns are missing: {missing_columns}"
            )

            logger.error(error_message)
            validation_errors.append(error_message)

        if unexpected_columns:
            warning_message = (
                f"Unexpected columns found: {unexpected_columns}"
            )

            logger.warning(warning_message)
            validation_warnings.append(warning_message)

        # ---------------------------------------------------------
        # 5. Check missing values
        # ---------------------------------------------------------
        missing_values_by_column = dataframe.isnull().sum()

        missing_value_count = int(
            missing_values_by_column.sum()
        )

        logger.info(
            "Total missing values: %s",
            missing_value_count,
        )

        if missing_value_count > 0:
            missing_percentage = (
                missing_value_count
                / (row_count * column_count)
                * 100
            ) if row_count > 0 and column_count > 0 else 100.0

            missing_message = (
                f"Missing values detected: {missing_value_count} "
                f"({missing_percentage:.2f}%)"
            )

            if (
                missing_percentage
                > self.config.max_missing_percentage
            ):
                logger.error(missing_message)
                validation_errors.append(missing_message)
            else:
                logger.warning(missing_message)
                validation_warnings.append(missing_message)

        # ---------------------------------------------------------
        # 6. Check duplicate rows
        # ---------------------------------------------------------
        duplicate_row_count = int(
            dataframe.duplicated().sum()
        )

        logger.info(
            "Duplicate rows: %s",
            duplicate_row_count,
        )

        if (
            duplicate_row_count > 0
            and not self.config.allow_duplicates
        ):
            duplicate_message = (
                f"Duplicate rows detected: {duplicate_row_count}"
            )

            logger.error(duplicate_message)
            validation_errors.append(duplicate_message)

        # ---------------------------------------------------------
        # 7. Check invalid numeric columns
        # ---------------------------------------------------------
        numeric_columns = dataframe.select_dtypes(
            include=["number"]
        ).columns.tolist()

        for column in numeric_columns:
            invalid_values = dataframe[column].isna().sum()

            if invalid_values > 0:
                invalid_numeric_columns.append(column)

        if invalid_numeric_columns:
            warning_message = (
                "Numeric columns contain missing values: "
                f"{invalid_numeric_columns}"
            )

            logger.warning(warning_message)
            validation_warnings.append(warning_message)

        # ---------------------------------------------------------
        # 8. Final validation status
        # ---------------------------------------------------------
        validation_status = len(validation_errors) == 0

        if validation_status:
            logger.info(
                "Data validation completed successfully"
            )
        else:
            logger.error(
                "Data validation failed with %s error(s)",
                len(validation_errors),
            )

        # ---------------------------------------------------------
        # 9. Create validation report
        # ---------------------------------------------------------
        validation_report = {
            "validation_status": validation_status,
            "ingested_data_path": str(ingested_data_path),
            "validation_report_path": str(validation_report_path),
            "row_count": row_count,
            "column_count": column_count,
            "missing_value_count": missing_value_count,
            "duplicate_row_count": duplicate_row_count,
            "missing_columns": missing_columns,
            "unexpected_columns": unexpected_columns,
            "invalid_numeric_columns": invalid_numeric_columns,
            "errors": validation_errors,
            "warnings": validation_warnings,
        }

        with open(
            validation_report_path,
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                validation_report,
                file,
                indent=4,
            )

        logger.info(
            "Validation report saved at: %s",
            validation_report_path,
        )

        # ---------------------------------------------------------
        # 10. Return artifact
        # ---------------------------------------------------------
        return DataValidationArtifact(
            artifact_name="data_validation_artifact",
            artifact_dir=self.config.artifact_dir,
            status=validation_status,
            message=(
                "Data validation completed successfully"
                if validation_status
                else "Data validation failed"
            ),
            ingested_data_path=ingested_data_path,
            validation_report_path=validation_report_path,
            validation_status=validation_status,
            row_count=row_count,
            column_count=column_count,
            missing_value_count=missing_value_count,
            duplicate_row_count=duplicate_row_count,
            missing_columns=missing_columns,
            unexpected_columns=unexpected_columns,
            invalid_numeric_columns=invalid_numeric_columns,
            validation_errors=validation_errors,
            validation_warnings=validation_warnings,
        )