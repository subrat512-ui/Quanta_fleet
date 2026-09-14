from dataclasses import dataclass
from pathlib import Path


@dataclass
class BaseConfig:
    """
    Base configuration shared by all pipeline stages.
    """

    pipeline_name: str

    pipeline_version: str

    artifact_dir: Path

    def create_directories(self) -> None:
        """
        Create the artifact directory for the stage.
        """

        self.artifact_dir.mkdir(
            parents=True,
            exist_ok=True,
        )