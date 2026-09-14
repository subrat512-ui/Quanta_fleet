"""Input readers for the GreenFleet ETL pipeline."""

from pathlib import Path

import pandas as pd

from greenfleet.logging.logger import logger


SUPPORTED_INPUT_SUFFIXES = {".csv"}


def extract_data(file_path: str | Path) -> pd.DataFrame:
    """Read a supported source file into a DataFrame."""
    path = Path(file_path).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"Dataset not found: {path}")

    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_INPUT_SUFFIXES:
        supported = ", ".join(sorted(SUPPORTED_INPUT_SUFFIXES))
        raise ValueError(f"Unsupported input format '{suffix}'. Supported formats: {supported}")

    try:
        logger.info("Extracting dataset from %s", path)
        frame = pd.read_csv(path)
    except Exception as exc:
        logger.exception("Failed to extract dataset from %s", path)
        raise RuntimeError(f"Failed to extract dataset: {path}") from exc

    if frame.empty:
        raise ValueError(f"Dataset is empty: {path}")
    logger.info("Extraction complete: %s rows, %s columns", len(frame), len(frame.columns))
    return frame


def extract_csv(file_path: str | Path) -> pd.DataFrame:
    """Extract the current GreenFleet raw CSV dataset."""
    path = Path(file_path)
    if path.suffix.lower() != ".csv":
        raise ValueError("extract_csv only accepts a .csv file")
    return extract_data(path)
