"""Orchestration entry point for the GreenFleet ETL workflow."""

from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter
from typing import Iterable

from greenfleet.logging.logger import logger
from greenfleet.pipeline.etl.extract import extract_data
from greenfleet.pipeline.etl.load import load_dataframe, write_audit_report
from greenfleet.pipeline.etl.transform import transform_dataframe
from greenfleet.pipeline.etl.validate import (
    CANONICAL_REQUIRED_COLUMNS,
    DEFAULT_REQUIRED_COLUMNS,
    validate_dataframe,
)


@dataclass(frozen=True)
class ETLResult:
    dataset_path: Path
    audit_path: Path
    input_rows: int
    output_rows: int
    duration_seconds: float
    validation: dict[str, object]
    transformation: dict[str, int]

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["dataset_path"] = str(self.dataset_path)
        result["audit_path"] = str(self.audit_path)
        return result


def run_etl(
    source_path: str | Path,
    output_path: str | Path,
    *,
    audit_path: str | Path | None = None,
    required_columns: Iterable[str] = DEFAULT_REQUIRED_COLUMNS,
) -> ETLResult:
    """Extract, validate, transform, and persist a maritime dataset."""
    started = perf_counter()
    source = Path(source_path)
    destination = Path(output_path)
    logger.info("Starting ETL pipeline for %s", source)

    raw = extract_data(source)
    validation = validate_dataframe(raw, required_columns)
    cleaned, transformation = transform_dataframe(raw)
    validate_dataframe(cleaned, CANONICAL_REQUIRED_COLUMNS)
    dataset_path = load_dataframe(cleaned, destination)

    report_path = Path(audit_path) if audit_path else destination.with_suffix(".audit.json")
    result = ETLResult(
        dataset_path=dataset_path,
        audit_path=report_path,
        input_rows=len(raw),
        output_rows=len(cleaned),
        duration_seconds=round(perf_counter() - started, 4),
        validation=validation.to_dict(),
        transformation=transformation.to_dict(),
    )
    write_audit_report(result.to_dict(), report_path)
    logger.info("ETL pipeline completed in %.2fs", result.duration_seconds)
    return result
