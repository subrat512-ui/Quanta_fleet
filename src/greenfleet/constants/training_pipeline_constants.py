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



# Existing constants...

DATA_VALIDATION_DIR_NAME = "02_validation"

DATA_VALIDATION_ARTIFACT_DIR = (
    ARTIFACTS_DIR / DATA_VALIDATION_DIR_NAME
)

VALIDATION_REPORT_FILE_NAME = "validation_report.json"

VALIDATION_REPORT_FILE = (
    DATA_VALIDATION_ARTIFACT_DIR / VALIDATION_REPORT_FILE_NAME
)




DATA_TRANSFORMATION_DIR_NAME = "data_transformation"

DATA_TRANSFORMATION_TRANSFORMED_DATA_DIR = "transformed_data"

DATA_TRANSFORMATION_TRANSFORMED_TRAIN_FILE_NAME = (
    "transformed_train.npz"
)

DATA_TRANSFORMATION_TRANSFORMED_TEST_FILE_NAME = (
    "transformed_test.npz"
)

DATA_TRANSFORMATION_PREPROCESSOR_FILE_NAME = (
    "preprocessor.pkl"
)

DATA_TRANSFORMATION_FEATURE_NAMES_FILE_NAME = (
    "feature_names.json"
)

DATA_TRANSFORMATION_REPORT_FILE_NAME = (
    "transformation_report.json"
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





# ============================================================
# Machine Learning Constants
# ============================================================

TARGET_COLUMN = "fuel_consumption_rate"

TRAIN_TEST_SPLIT_RATIO = 0.2

RANDOM_STATE = 42


# ============================================================
# Dataset Feature Columns
# ============================================================

NUMERICAL_FEATURE_COLUMNS = [
    "sailing_speed",
    "displacement",
    "trim",
    "wind_speed",
    "wind_direction_relative",
    "combined_wave_height",
    "combined_wave_period",
    "sea_current_speed",
    "sea_current_direction_relative",
    "sea_water_temperature",
]

CATEGORICAL_FEATURE_COLUMNS = [
    "vessel_type",
]