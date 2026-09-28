"""Fixed, bounded FuelCast classical search contract."""

SEED = 42
CLASSICAL_FEATURES = (
    "speed_over_ground", "wind_speed", "wind_direction_sin",
    "wind_direction_cos", "wave_height", "wave_period", "current_speed",
)
CANDIDATES = ("ridge", "random_forest", "gradient_boosting", "xgboost")
QUICK_ROWS_PER_VESSEL = 1000

SEARCHES = {
    "quick": {
        "ridge": ("grid", {"alpha": [0.1, 1.0, 10.0]}, 3),
        "random_forest": ("random", {
            "n_estimators": [40, 60], "max_depth": [8, 12],
            "min_samples_split": [2, 5], "min_samples_leaf": [2, 4],
            "max_features": [0.7, 1.0],
        }, 2),
        "gradient_boosting": ("random", {
            "n_estimators": [40, 60], "learning_rate": [0.05, 0.1],
            "max_depth": [2, 3], "min_samples_split": [2, 5],
            "subsample": [0.7, 1.0],
        }, 2),
        "xgboost": ("random", {
            "n_estimators": [60, 100], "learning_rate": [0.05, 0.1],
            "max_depth": [3, 5], "min_child_weight": [1, 5],
            "subsample": [0.7, 1.0], "colsample_bytree": [0.7, 1.0],
            "reg_alpha": [0.0, 0.1], "reg_lambda": [1.0, 5.0],
        }, 2),
    },
    "normal": {
        "ridge": ("grid", {"alpha": [0.01, 0.1, 1.0, 10.0, 100.0]}, 5),
        "random_forest": ("random", {
            "n_estimators": [60, 100, 120], "max_depth": [8, 12],
            "min_samples_split": [2, 5, 10], "min_samples_leaf": [2, 4],
            "max_features": [0.7, 1.0],
        }, 6),
        "gradient_boosting": ("random", {
            "n_estimators": [60, 90, 120], "learning_rate": [0.03, 0.07, 0.1],
            "max_depth": [2, 3], "min_samples_split": [2, 5, 10],
            "subsample": [0.7, 1.0],
        }, 6),
        "xgboost": ("random", {
            "n_estimators": [80, 140, 200], "learning_rate": [0.03, 0.07, 0.1],
            "max_depth": [3, 5], "min_child_weight": [1, 5, 10],
            "subsample": [0.7, 1.0], "colsample_bytree": [0.7, 1.0],
            "reg_alpha": [0.0, 0.1], "reg_lambda": [1.0, 5.0],
        }, 8),
    },
}
