from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def convert_paths_to_strings(value: Any) -> Any:
    """
    Convert Path objects into strings so that
    the artifact can be serialized into JSON.
    """

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, dict):
        return {
            key: convert_paths_to_strings(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [
            convert_paths_to_strings(item)
            for item in value
        ]

    return value


@dataclass(kw_only=True)
class BaseArtifact:
    """
    Base artifact shared by all pipeline stages.
    """

    artifact_name: str
    artifact_dir: Path

    status: bool = True
    message: str = ""

    created_at: str = field(
        default_factory=lambda: datetime.now(
            timezone.utc
        ).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        """
        Convert artifact object into a dictionary.
        """

        artifact_dict = asdict(self)

        return convert_paths_to_strings(artifact_dict)