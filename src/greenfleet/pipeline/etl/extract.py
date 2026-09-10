"""Input readers for the GreenFleet ETL pipeline."""

from pathlib import Path

import pandas as pd

from greenfleet.logging.logger import logger


SUPPORTED_INPUT_SUFFIXES = {".parquet", ".csv"}


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
        frame = pd.read_parquet(path) if suffix == ".parquet" else pd.read_csv(path)
    except Exception as exc:
        logger.exception("Failed to extract dataset from %s", path)
        raise RuntimeError(f"Failed to extract dataset: {path}") from exc

    if frame.empty:
        raise ValueError(f"Dataset is empty: {path}")
    logger.info("Extraction complete: %s rows, %s columns", len(frame), len(frame.columns))
    return frame


def extract_parquet(file_path: str | Path) -> pd.DataFrame:
    """Backward-compatible Parquet-specific extraction entry point."""
    path = Path(file_path)
    if path.suffix.lower() != ".parquet":
        raise ValueError("extract_parquet only accepts a .parquet file")
    return extract_data(path)
