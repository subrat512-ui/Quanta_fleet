"""Result of an attempted FuelCast MongoDB persistence stage."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FuelCastMongoArtifact:
    report_path: Path
    status: str
    dataset_version: str | None
    expected_rows: int | None
    verified_loaded_rows: int | None
