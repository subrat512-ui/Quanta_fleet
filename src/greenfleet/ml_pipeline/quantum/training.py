"""End-to-end QPSO-SVR training for fuel-consumption regression."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold, GroupShuffleSplit, KFold, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.svm import SVR

from greenfleet.constants.training_pipeline_constants import (
    CATEGORICAL_FEATURE_COLUMNS,
    NUMERICAL_FEATURE_COLUMNS,
    TARGET_COLUMN,
)

from .qpso_svr import QPSOConfig, QPSOSVRTuner


@dataclass(frozen=True)
class QuantumTrainingResult:
    model_path: Path
    metrics_path: Path
    metrics: dict[str, float]
    best_params: dict[str, float]
    warnings: list[str]


def _build_pipeline(
    numerical_features: Sequence[str],
    categorical_features: Sequence[str],
    svr_params: dict[str, float],
) -> Pipeline:
    transformers = []
    if numerical_features:
        numerical = Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
            ]
        )
        transformers.append(("numerical", numerical, list(numerical_features)))
    if categorical_features:
        categorical = Pipeline(
            [
                ("imputer", SimpleImputer(strategy="most_frequent")),
                (
                    "encoder",
                    OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                ),
            ]
        )
        transformers.append(("categorical", categorical, list(categorical_features)))
    if not transformers:
        raise ValueError("at least one feature column is required")

    return Pipeline(
        [
            (
                "preprocessor",
                ColumnTransformer(transformers=transformers, remainder="drop"),
            ),
            ("regressor", SVR(kernel="rbf", **svr_params)),
        ]
    )


def _quality_warnings(data: pd.DataFrame, numerical_features: Sequence[str], target: str) -> list[str]:
    warnings: list[str] = []
    numeric = data[[*numerical_features, target]].apply(pd.to_numeric, errors="coerce")
    correlations = numeric.corr()[target].drop(target).abs().dropna()
    nearly_exact = correlations[correlations > 0.9999].index.tolist()
    if nearly_exact:
        warnings.append(
            "Target has absolute correlation above 0.9999 with: "
            + ", ".join(nearly_exact)
            + ". Check for synthetic coupling or target leakage."
        )
    duplicate_pairs: list[str] = []
    feature_corr = numeric[list(numerical_features)].corr().abs()
    for row_index, left in enumerate(feature_corr.columns):
        for right in feature_corr.columns[row_index + 1 :]:
            if feature_corr.loc[left, right] > 0.9999:
                duplicate_pairs.append(f"{left}/{right}")
    if duplicate_pairs:
        warnings.append(
            "Near-duplicate numerical feature pairs detected: "
            + ", ".join(duplicate_pairs[:10])
            + (" ..." if len(duplicate_pairs) > 10 else "")
        )
    return warnings


def train_quantum_svr(
    csv_path: str | Path,
    output_dir: str | Path,
    *,
    numerical_features: Sequence[str] = NUMERICAL_FEATURE_COLUMNS,
    categorical_features: Sequence[str] = CATEGORICAL_FEATURE_COLUMNS,
    target_column: str = TARGET_COLUMN,
    group_column: str | None = None,
    test_size: float = 0.2,
    cv_splits: int = 3,
    qpso_config: QPSOConfig | None = None,
) -> QuantumTrainingResult:
    """Train and persist a quantum-inspired QPSO-tuned SVR pipeline."""
    csv_path = Path(csv_path)
    output_dir = Path(output_dir)
    data = pd.read_csv(csv_path)
    features = [*numerical_features, *categorical_features]
    required = set(features + [target_column])
    if group_column:
        required.add(group_column)
    missing = sorted(required.difference(data.columns))
    if missing:
        raise ValueError(f"missing required columns: {missing}")
    if data[target_column].isna().any():
        raise ValueError("target column contains missing values")
    if len(data) < 10:
        raise ValueError("at least 10 records are required")
    if not 0.0 < test_size < 1.0:
        raise ValueError("test_size must be between 0 and 1")

    X = data[features].copy()
    y = pd.to_numeric(data[target_column], errors="raise").astype(float)
    groups = data[group_column] if group_column else None
    warnings = _quality_warnings(data, numerical_features, target_column)

    if groups is not None:
        unique_groups = int(groups.nunique())
        if unique_groups < max(cv_splits + 1, 3):
            raise ValueError(
                f"group_column needs at least {max(cv_splits + 1, 3)} unique groups"
            )
        splitter = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=42)
        train_index, test_index = next(splitter.split(X, y, groups))
        X_train, X_test = X.iloc[train_index], X.iloc[test_index]
        y_train, y_test = y.iloc[train_index], y.iloc[test_index]
        train_groups = groups.iloc[train_index]
        cv = list(GroupKFold(n_splits=cv_splits).split(X_train, y_train, train_groups))
        split_strategy = "grouped"
    else:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42
        )
        if len(X_train) < cv_splits:
            raise ValueError("training set is smaller than cv_splits")
        cv = list(KFold(n_splits=cv_splits, shuffle=True, random_state=42).split(X_train))
        split_strategy = "random"

    def objective(params: dict[str, float]) -> float:
        fold_errors: list[float] = []
        for fold_train, fold_valid in cv:
            model = _build_pipeline(numerical_features, categorical_features, params)
            model.fit(X_train.iloc[fold_train], y_train.iloc[fold_train])
            prediction = model.predict(X_train.iloc[fold_valid])
            fold_errors.append(float(mean_absolute_error(y_train.iloc[fold_valid], prediction)))
        return float(np.mean(fold_errors))

    config = qpso_config or QPSOConfig()
    search = QPSOSVRTuner(config).optimize(objective)
    model = _build_pipeline(numerical_features, categorical_features, search.best_params)
    model.fit(X_train, y_train)
    prediction = model.predict(X_test)
    metrics = {
        "mae": float(mean_absolute_error(y_test, prediction)),
        "rmse": float(np.sqrt(mean_squared_error(y_test, prediction))),
        "r2_score": float(r2_score(y_test, prediction)),
        "cv_mae": float(search.best_score),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    model_path = output_dir / "quantum_qpso_svr.pkl"
    metrics_path = output_dir / "quantum_qpso_svr_metrics.json"
    joblib.dump(model, model_path)
    report = {
        "model": "QPSO-tuned RBF SVR",
        "quantum_inspired": True,
        "hardware": "classical",
        "source_csv": str(csv_path),
        "target": target_column,
        "numerical_features": list(numerical_features),
        "categorical_features": list(categorical_features),
        "group_column": group_column,
        "split_strategy": split_strategy,
        "train_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
        "best_params": search.best_params,
        "metrics": metrics,
        "search_config": asdict(config),
        "evaluations": search.evaluations,
        "search_history": search.history,
        "data_quality_warnings": warnings,
    }
    metrics_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return QuantumTrainingResult(model_path, metrics_path, metrics, search.best_params, warnings)
