"""Typed execution settings for the FuelCast VQR prototype."""

from dataclasses import dataclass
from pathlib import Path

from greenfleet.constants.fuelcast_vqr import VQR_MODES, VQR_SEED


@dataclass(frozen=True)
class FuelCastVQRConfig:
    run_dir: Path
    mode: str
    expected_version: str
    expected_canonical_sha256: str
    seed: int = VQR_SEED
    resume_checkpoint: Path | None = None

    def __post_init__(self) -> None:
        if self.mode not in VQR_MODES:
            raise ValueError(f"Unknown VQR mode: {self.mode}")
        if not self.run_dir.is_absolute():
            raise ValueError("FuelCast run directory must be explicit and absolute")
        if not self.expected_version or len(self.expected_canonical_sha256) != 64:
            raise ValueError("FuelCast expected version and canonical SHA-256 are required")
        if self.resume_checkpoint is not None and not self.resume_checkpoint.is_absolute():
            raise ValueError("FuelCast VQR resume checkpoint must be an absolute candidate directory")
