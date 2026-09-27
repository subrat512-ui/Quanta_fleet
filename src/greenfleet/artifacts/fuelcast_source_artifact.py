"""Result of a successfully published FuelCast source stage."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FuelCastSourceArtifact:
    snapshot_path: Path
    manifest_path: Path
    dataset_version: str
    row_counts: dict[str, int]

    @property
    def total_rows(self) -> int:
        return sum(self.row_counts.values())
