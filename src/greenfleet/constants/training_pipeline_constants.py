from pathlib import Path


# ==================================================
# PROJECT DIRECTORIES
# ==================================================

PROJECT_ROOT = Path(__file__).resolve().parents[3]

SRC_DIR = PROJECT_ROOT / "src"

DATA_DIR = PROJECT_ROOT / "data"

ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"


# ==================================================
# PIPELINE INFORMATION
# ==================================================

PIPELINE_NAME = "greenfleet_fuel_prediction"

PIPELINE_VERSION = "1.0"


# ==================================================
# SOURCE DATA
# ==================================================

FINAL_DATA_DIR = DATA_DIR / "final"

SOURCE_DATA_FILE_NAME = (
    "maritime_fuel_clean.csv"
)

SOURCE_DATA_FILE = (
    FINAL_DATA_DIR / SOURCE_DATA_FILE_NAME
)


# ==================================================
# DATA INGESTION
# ==================================================

DATA_INGESTION_DIR_NAME = "01_ingestion"

DATA_INGESTION_ARTIFACT_DIR = (
    ARTIFACTS_DIR / DATA_INGESTION_DIR_NAME
)

INGESTED_DATA_FILE_NAME = (
    "ingested_data.csv"
)

INGESTED_DATA_FILE = (
    DATA_INGESTION_ARTIFACT_DIR
    / INGESTED_DATA_FILE_NAME
)

INGESTION_METADATA_FILE_NAME = (
    "ingestion_metadata.json"
)

INGESTION_METADATA_FILE = (
    DATA_INGESTION_ARTIFACT_DIR
    / INGESTION_METADATA_FILE_NAME
)


# ==================================================
# COMMON FILE NAMES
# ==================================================

ARTIFACT_METADATA_FILE_NAME = (
    "artifact_metadata.json"
)

SUCCESS_MESSAGE = (
    "Data ingestion completed successfully."
)

FAILURE_MESSAGE = (
    "Data ingestion failed."
)