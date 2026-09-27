"""Paths and row counts for a published canonical FuelCast ETL stage."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FuelCastETLArtifact:
    canonical_path: Path
    audit_path: Path
    dataset_version: str
    row_counts: dict[str, int]

    @property
    def total_rows(self) -> int:
        return sum(self.row_counts.values())
