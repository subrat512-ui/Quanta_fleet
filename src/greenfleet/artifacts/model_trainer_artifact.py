from dataclasses import dataclass
from pathlib import Path


@dataclass
class ModelTrainerArtifact:
    trained_model_file_path: Path
    model_name: str
    mae: float
    rmse: float
    r2_score: float
    is_training_successful: bool
    message: str = ""
    metrics: dict[str, dict[str, float]] | None = None
