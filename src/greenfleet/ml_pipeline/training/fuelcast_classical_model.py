"""Strict loader for a fitted Phase 5 candidate."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn

from greenfleet.constants.fuelcast_classical import CLASSICAL_FEATURES
from greenfleet.ml_pipeline.training.fuelcast_data import SavedValidationSplit, sha256_file


@dataclass(frozen=True)
class LoadedClassicalCandidate:
    model: object
    manifest: dict

    def predict(self, features: pd.DataFrame) -> np.ndarray:
        if not isinstance(features, pd.DataFrame) or list(features.columns) != list(CLASSICAL_FEATURES):
            raise ValueError("FuelCast transformed input must have exactly seven named columns in order")
        values = features.to_numpy(dtype=np.float64)
        if values.ndim != 2 or not np.isfinite(values).all():
            raise ValueError("FuelCast transformed input must be finite")
        result = np.asarray(self.model.predict(features), dtype=np.float64).reshape(-1)
        if result.shape != (len(features),) or not np.isfinite(result).all():
            raise ValueError("FuelCast candidate produced invalid predictions")
        return result


def load_classical_candidate(
    candidate_dir: Path, split: SavedValidationSplit,
) -> LoadedClassicalCandidate:
    candidate_dir = Path(candidate_dir).resolve(strict=True)
    manifest = json.loads((candidate_dir / "candidate_manifest.json").read_text(encoding="utf-8"))
    if (manifest.get("feature_order") != list(CLASSICAL_FEATURES)
            or manifest.get("target") != "fuel_consumption_kg_s"
            or manifest.get("target_unit") != "kg/s"
            or manifest.get("model_family") != "classical"):
        raise ValueError("FuelCast candidate schema mismatch")
    versions = manifest.get("dependency_versions", {})
    if (versions.get("scikit_learn") != sklearn.__version__
            or versions.get("numpy") != np.__version__
            or versions.get("pandas") != pd.__version__
            or versions.get("joblib") != joblib.__version__):
        raise ValueError("FuelCast candidate dependency version mismatch")
    if (manifest.get("run_id") != split.run_dir.name
            or manifest.get("dataset_version") != split.dataset_version
            or manifest.get("canonical_sha256") != split.canonical_sha256
            or manifest.get("feature_schema_sha256") != split.schema_sha256
            or manifest.get("split_manifest_sha256") != split.split_manifest_sha256
            or manifest.get("phase4_artifact_sha256") != split.source_hashes):
        raise ValueError("FuelCast candidate source mismatch")
    model_name = manifest.get("model_file")
    if model_name not in {"model.joblib", "model.json"}:
        raise ValueError("FuelCast candidate model filename mismatch")
    model_path = candidate_dir / model_name
    if sha256_file(model_path) != manifest.get("artifact_sha256", {}).get(model_name):
        raise ValueError("FuelCast candidate model hash mismatch")
    for name in ("search_results.json", "validation_predictions.npz"):
        if sha256_file(candidate_dir / name) != manifest.get("artifact_sha256", {}).get(name):
            raise ValueError(f"FuelCast candidate {name} hash mismatch")
    if manifest["candidate"] == "xgboost":
        try:
            import xgboost
        except Exception as exc:
            raise RuntimeError(
                "XGBoost is required; install with python -m pip install -r requirements.txt "
                "and ensure the OpenMP runtime (libomp on macOS) is available"
            ) from exc
        if manifest.get("dependency_versions", {}).get("xgboost") != xgboost.__version__:
            raise ValueError("FuelCast candidate XGBoost version mismatch")
        model = xgboost.XGBRegressor()
        model.load_model(model_path)
    else:
        model = joblib.load(model_path)
    return LoadedClassicalCandidate(model, manifest)
