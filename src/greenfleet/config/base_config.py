from dataclasses import dataclass
from pathlib import Path

from greenfleet.constants.training_pipeline_constants import (
    PIPELINE_NAME,
    PIPELINE_VERSION,
    ARTIFACTS_DIR,
)


@dataclass
class BaseConfig:
    """
    Base configuration shared by all pipeline stages.
    """

    pipeline_name: str = PIPELINE_NAME
    pipeline_version: str = PIPELINE_VERSION
    artifact_dir: Path = ARTIFACTS_DIR

    def create_directories(self) -> None:
        """
        Create the artifact directory for the stage.
        """
        self.artifact_dir.mkdir(
            parents=True,
            exist_ok=True,
        )