"""Validated settings for a single classical FuelCast experiment."""

from dataclasses import dataclass
from pathlib import Path

from greenfleet.constants.fuelcast_classical import SEARCHES, SEED


@dataclass(frozen=True)
class FuelCastClassicalConfig:
    run_dir: Path
    mode: str
    expected_version: str
    expected_canonical_sha256: str
    seed: int = SEED

    def __post_init__(self) -> None:
        if not self.run_dir.is_absolute():
            raise ValueError("--run-dir must be an absolute path")
        if self.mode not in SEARCHES:
            raise ValueError(f"Unknown classical mode: {self.mode}")
        if not self.expected_version or not self.expected_canonical_sha256:
            raise ValueError("Expected dataset version and canonical SHA-256 are required")
