from pathlib import Path

import pandas as pd

from greenfleet.exceptions import GreenFleetError
from greenfleet.logging import logger


def extract_parquet(file_path: str) -> pd.DataFrame:
    """
    Extract raw vessel data from a Parquet file.
    """

    path = Path(file_path)

    if not path.exists():
        raise GreenFleetError(
            f"Dataset not found: {path}"
        )

    try:
        logger.logging.info(
            f"Starting data extraction from {path}"
        )

        df = pd.read_parquet(path)

        logger.logging.info(
            f"Data extraction successful. Shape: {df.shape}"
        )

        return df

    except Exception as e:
        logger.logging.error(
            f"Failed to extract dataset: {e}"
        )
        raise GreenFleetError(
            "Failed to extract vessel dataset",
            cause=e
        )