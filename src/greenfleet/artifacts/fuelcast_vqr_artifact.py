"""Paths returned by the simulator VQR stage."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FuelCastVQRArtifact:
    candidate_dir: Path
    manifest_path: Path
    weights_path: Path
    metrics_path: Path
    predictions_path: Path
