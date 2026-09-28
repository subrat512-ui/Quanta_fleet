"""Reconstruct simulator VQR inference from circuits, weights and scalers."""

from __future__ import annotations

import importlib.metadata
import json
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from greenfleet.constants.fuelcast_vqr import VQR_BATCH_SIZE, VQR_FEATURES, VQR_TARGET
from greenfleet.ml_pipeline.training.fuelcast_data import sha256_file


def quantum_dependencies():
    """Delay optional quantum imports until VQR execution is requested."""
    try:
        from qiskit import QuantumCircuit
        from qiskit.circuit import ParameterVector
        from qiskit.circuit.library import real_amplitudes
        from qiskit.quantum_info import SparsePauliOp
        from qiskit_machine_learning.algorithms import VQR
        from qiskit_machine_learning.neural_networks import EstimatorQNN
        from qiskit_machine_learning.optimizers import COBYLA
        from qiskit_machine_learning.primitives import QMLEstimator
    except (ImportError, OSError) as exc:
        raise RuntimeError(
            "Simulator VQR requires optional quantum dependencies; install with "
            "python -m pip install -r requirements-vqr.txt"
        ) from exc
    return (QuantumCircuit, ParameterVector, real_amplitudes, SparsePauliOp,
            VQR, EstimatorQNN, COBYLA, QMLEstimator)


def build_vqr_circuits(ansatz_repetitions: int = 1):
    """Six input RY rotations with one or two shallow ansatz layers."""
    if ansatz_repetitions not in (1, 2):
        raise ValueError("FuelCast VQR supports one or two ansatz repetitions")
    (QuantumCircuit, ParameterVector, real_amplitudes, SparsePauliOp,
     _, _, _, _) = quantum_dependencies()
    angles = ParameterVector("x", len(VQR_FEATURES))
    feature_map = QuantumCircuit(len(VQR_FEATURES), name="fuelcast_ry")
    for qubit, angle in enumerate(angles):
        feature_map.ry(angle, qubit)
    ansatz = real_amplitudes(
        len(VQR_FEATURES), reps=ansatz_repetitions, entanglement="linear",
        skip_final_rotation_layer=False, parameter_prefix="theta",
    )
    paulis = []
    for qubit in range(len(VQR_FEATURES)):
        label = "I" * (len(VQR_FEATURES) - 1 - qubit) + "Z" + "I" * qubit
        paulis.append((label, 1.0 / len(VQR_FEATURES)))
    observable = SparsePauliOp.from_list(paulis)
    if (feature_map.num_parameters != len(VQR_FEATURES)
            or ansatz.num_parameters != (ansatz_repetitions + 1) * len(VQR_FEATURES)
            or ansatz.num_qubits != len(VQR_FEATURES)):
        raise RuntimeError("FuelCast VQR circuit width or parameter count changed")
    return feature_map, ansatz, observable


def circuit_configuration() -> dict:
    return {
        "algorithm": "VQR", "num_qubits": 6,
        "feature_map": {"class": "QuantumCircuit", "encoding": "RY",
                        "repetitions": 1, "input_parameters": 6,
                        "qubit_feature_order": list(VQR_FEATURES),
                        "angle_ranges": [[0, "pi"], [0, "pi"], [0, "2pi"],
                                         [0, "pi"], [0, "pi"], [0, "pi"]]},
        "ansatz": {"factory": "real_amplitudes", "repetitions": 1,
                   "entanglement": "linear", "gate": "CX", "weights": 12,
                   "skip_final_rotation_layer": False},
        "observable": {"name": "mean_single_qubit_Z", "terms": 6,
                       "coefficient": 1.0 / 6.0},
        "estimator": "QMLEstimator", "default_precision": 0.0,
        "backend": "simulator", "real_quantum_hardware": False,
    }


def _version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError as exc:
        raise RuntimeError(
            "Simulator VQR dependencies are missing; install with "
            "python -m pip install -r requirements-vqr.txt"
        ) from exc


def dependency_versions() -> dict[str, str]:
    return {name: _version(name) for name in (
        "qiskit", "qiskit-machine-learning", "numpy", "scipy", "scikit-learn", "joblib",
    )}


def validate_angles(features: pd.DataFrame) -> np.ndarray:
    if not isinstance(features, pd.DataFrame) or list(features.columns) != list(VQR_FEATURES):
        raise ValueError("FuelCast VQR angles require six named columns in schema order")
    values = features.to_numpy(dtype=np.float64)
    if values.ndim != 2 or not np.isfinite(values).all():
        raise ValueError("FuelCast VQR angles must be finite")
    if (np.any(values[:, (0, 1, 3, 4, 5)] < -1e-12)
            or np.any(values[:, (0, 1, 3, 4, 5)] > np.pi + 1e-12)
            or np.any(values[:, 2] < -1e-12)
            or np.any(values[:, 2] > 2 * np.pi + 1e-12)):
        raise ValueError("FuelCast VQR angles are outside the saved Phase 4 ranges")
    return values


@dataclass
class LoadedVQRCandidate:
    qnn: object
    weights: np.ndarray
    angle_preprocessor: object
    target_scaler: object
    manifest: dict

    def predict_angles(self, features: pd.DataFrame) -> np.ndarray:
        values = validate_angles(features)
        chunks = []
        for start in range(0, len(values), VQR_BATCH_SIZE):
            result = np.asarray(
                self.qnn.forward(values[start:start + VQR_BATCH_SIZE], self.weights),
                dtype=np.float64,
            ).reshape(-1)
            if len(result) != min(VQR_BATCH_SIZE, len(values) - start):
                raise ValueError("FuelCast VQR prediction shape mismatch")
            if not np.isfinite(result).all() or np.any(np.abs(result) > 1 + 1e-8):
                raise ValueError("FuelCast VQR returned invalid expectation values")
            chunks.append(np.clip(result, -1, 1))  # Numerical tolerance only.
        expectation = np.concatenate(chunks) if chunks else np.empty(0, dtype=np.float64)
        kg_s = self.target_scaler.inverse_transform(expectation.reshape(-1, 1)).reshape(-1)
        if kg_s.shape != (len(values),) or not np.isfinite(kg_s).all():
            raise ValueError("FuelCast VQR returned invalid kg/s predictions")
        return kg_s

    def predict(self, canonical_features: pd.DataFrame) -> np.ndarray:
        """Predict one or more raw canonical rows without fitting any scaler."""
        if (not isinstance(canonical_features, pd.DataFrame)
                or list(canonical_features.columns) != list(VQR_FEATURES)):
            raise ValueError("FuelCast VQR inference requires six canonical columns in order")
        raw = canonical_features.to_numpy(dtype=np.float64)
        if np.isinf(raw).any():
            raise ValueError("FuelCast VQR canonical inputs must not contain infinity")
        angles = self.angle_preprocessor.transform(raw)
        return self.predict_angles(pd.DataFrame(angles, columns=VQR_FEATURES))


def load_vqr_candidate(candidate_dir: Path, expected_source=None) -> LoadedVQRCandidate:
    """Verify artifact integrity and build a new QNN without fitting."""
    candidate_dir = Path(candidate_dir).resolve(strict=True)
    manifest_path = candidate_dir / "candidate_manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError("FuelCast VQR candidate manifest must be a regular file")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (manifest.get("candidate") != "vqr" or manifest.get("model_family") != "quantum"
            or manifest.get("algorithm") != "VQR" or manifest.get("backend") != "simulator"
            or manifest.get("real_quantum_hardware") is not False
            or manifest.get("feature_order") != list(VQR_FEATURES)
            or manifest.get("target") != VQR_TARGET or manifest.get("target_unit") != "kg/s"):
        raise ValueError("FuelCast VQR candidate schema or labels mismatch")
    if expected_source is not None and (
            manifest.get("run_id") != expected_source.run_dir.name
            or manifest.get("dataset_version") != expected_source.dataset_version
            or manifest.get("canonical_sha256") != expected_source.canonical_sha256
            or manifest.get("feature_schema_sha256") != expected_source.schema_sha256
            or manifest.get("split_manifest_sha256") != expected_source.split_manifest_sha256
            or manifest.get("phase4_artifact_sha256") != expected_source.source_hashes):
        raise ValueError("FuelCast VQR candidate source mismatch")
    expected_files = {"circuit_config.json", "weights.npz", "vqr_preprocessor.pkl",
                      "vqr_target_scaler.pkl", "feature_schema.json", "sample_manifest.json",
                      "optimizer_history.json", "attempt_manifest.json",
                      "validation_predictions.npz",
                      "validation_metrics.json"}
    if set(manifest.get("artifact_sha256", {})) != expected_files:
        raise ValueError("FuelCast VQR candidate artifact set mismatch")
    if manifest.get("feature_schema_sha256") != manifest["artifact_sha256"]["feature_schema.json"]:
        raise ValueError("FuelCast VQR copied feature schema hash mismatch")
    source_hashes = manifest.get("phase4_artifact_sha256", {})
    for name in ("vqr_preprocessor.pkl", "vqr_target_scaler.pkl"):
        if source_hashes.get(name) != manifest["artifact_sha256"][name]:
            raise ValueError(f"FuelCast VQR copied {name} hash mismatch")
    for name in sorted(expected_files):
        path = candidate_dir / name
        if (path.is_symlink() or not path.is_file()
                or path.resolve(strict=True).parent != candidate_dir
                or sha256_file(path) != manifest["artifact_sha256"][name]):
            raise ValueError(f"FuelCast VQR candidate {name} hash mismatch")
    if manifest.get("dependency_versions") != dependency_versions():
        raise ValueError("FuelCast VQR dependency version mismatch")
    config = json.loads((candidate_dir / "circuit_config.json").read_text(encoding="utf-8"))
    if config != circuit_configuration():
        raise ValueError("FuelCast VQR circuit configuration mismatch")
    schema = json.loads((candidate_dir / "feature_schema.json").read_text(encoding="utf-8"))
    if (schema.get("vqr_features") != list(VQR_FEATURES)
            or schema.get("target") != VQR_TARGET):
        raise ValueError("FuelCast VQR saved feature schema mismatch")
    with np.load(candidate_dir / "weights.npz", allow_pickle=False) as source:
        if set(source.files) != {"weights"}:
            raise ValueError("FuelCast VQR weight artifact schema mismatch")
        weights = np.asarray(source["weights"], dtype=np.float64)
    if weights.shape != (12,) or not np.isfinite(weights).all():
        raise ValueError("FuelCast VQR weight vector mismatch")
    angle_preprocessor = joblib.load(candidate_dir / "vqr_preprocessor.pkl")
    target_scaler = joblib.load(candidate_dir / "vqr_target_scaler.pkl")
    if (getattr(target_scaler, "feature_range", None) != (-1, 1)
            or target_scaler.data_max_[0] <= target_scaler.data_min_[0]):
        raise ValueError("FuelCast VQR target scaler is degenerate")
    (_, _, _, _, _, EstimatorQNN, _, QMLEstimator) = quantum_dependencies()
    feature_map, ansatz, observable = build_vqr_circuits()
    qnn = EstimatorQNN(
        circuit=feature_map.compose(ansatz), estimator=QMLEstimator(default_precision=0.0),
        observables=observable, input_params=list(feature_map.parameters),
        weight_params=list(ansatz.parameters),
    )
    return LoadedVQRCandidate(qnn, weights, angle_preprocessor, target_scaler, manifest)
