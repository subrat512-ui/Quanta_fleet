"""Fixed simulator VQR prototype contract."""

from greenfleet.constants.fuelcast import CANONICAL_FEATURES

VQR_FEATURES = tuple(CANONICAL_FEATURES)
VQR_TARGET = "fuel_consumption_kg_s"
VQR_SEED = 42
VQR_BATCH_SIZE = 256
VQR_VALIDATION_WALL_SECONDS = 3600
VQR_MODES = {
    "quick": {"training_rows": 60, "maxiter": 14, "fit_wall_seconds": 600},
    "normal": {"training_rows": 600, "maxiter": 80, "fit_wall_seconds": 7200},
}
