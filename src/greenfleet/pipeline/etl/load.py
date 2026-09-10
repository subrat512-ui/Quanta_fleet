"""Output writers for the GreenFleet ETL pipeline."""

import json
from pathlib import Path
from typing import Mapping

import pandas as pd

from greenfleet.logging.logger import logger


def load_dataframe(frame: pd.DataFrame, output_path: str | Path) -> Path:
    """Write a DataFrame atomically as Parquet or CSV and return its path."""
    destination = Path(output_path)
    suffix = destination.suffix.lower()
    if suffix not in {".parquet", ".csv"}:
        raise ValueError("Output path must end in .parquet or .csv")

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.stem}.tmp{suffix}")
    try:
        if suffix == ".parquet":
            frame.to_parquet(temporary, index=False)
        else:
            frame.to_csv(temporary, index=False)
        temporary.replace(destination)
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        logger.exception("Failed to write transformed dataset to %s", destination)
        raise RuntimeError(f"Failed to load transformed dataset: {destination}") from exc

    logger.info("Loaded transformed dataset to %s", destination)
    return destination


def write_audit_report(report: Mapping[str, object], output_path: str | Path) -> Path:
    """Persist a JSON audit report beside a transformed dataset."""
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    return destination
