"""Paths to one published classical candidate."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FuelCastClassicalArtifact:
    candidate_dir: Path
    manifest_path: Path
    search_results_path: Path
    predictions_path: Path
    model_path: Path
