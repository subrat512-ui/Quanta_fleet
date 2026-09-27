"""FuelCast source contract. Canonical renaming belongs to the ETL stage."""

DATASET_ID = "krohnedigital/FuelCast"
EXPECTED_CONFIGS = ("cps_poseidon", "cps_triton", "oss_ceto")
SOURCE_SPLIT = "train"
SOURCE_LICENSE = "CC BY-NC-ND 4.0"
SOURCE_TIME_COLUMN = "index"
SOURCE_MODEL_COLUMNS = (
    "Ship_SpeedOverGround",
    "Weather_WindSpeed10M",
    "Weather_WindDirection10M",
    "Weather_WaveHeight",
    "Weather_WavePeriod",
    "Weather_OceanCurrentVelocity",
    "Consumer_Total_MomentaryFuel",
)
REQUIRED_SOURCE_COLUMNS = (SOURCE_TIME_COLUMN, *SOURCE_MODEL_COLUMNS)
RAW_COLUMNS = ("vessel_id", "time_index", *SOURCE_MODEL_COLUMNS)
