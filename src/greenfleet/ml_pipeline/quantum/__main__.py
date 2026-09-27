"""Command line entry point for QPSO-SVR training."""

from __future__ import annotations

import argparse
import json

from .qpso_svr import QPSOConfig
from .training import train_quantum_svr


def _columns(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Train a QPSO-tuned SVR fuel predictor")
    parser.add_argument("csv_path")
    parser.add_argument("--output-dir", default="artifacts/04_quantum_model")
    parser.add_argument("--target", default="fuel_consumption_rate")
    parser.add_argument("--group-column")
    parser.add_argument("--numerical-features", type=_columns)
    parser.add_argument("--categorical-features", type=_columns)
    parser.add_argument("--population-size", type=int, default=16)
    parser.add_argument("--iterations", type=int, default=25)
    parser.add_argument("--cv-splits", type=int, default=3)
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()

    kwargs = {}
    if args.numerical_features is not None:
        kwargs["numerical_features"] = args.numerical_features
    if args.categorical_features is not None:
        kwargs["categorical_features"] = args.categorical_features
    result = train_quantum_svr(
        args.csv_path,
        args.output_dir,
        target_column=args.target,
        group_column=args.group_column,
        cv_splits=args.cv_splits,
        qpso_config=QPSOConfig(
            population_size=args.population_size,
            iterations=args.iterations,
            random_state=args.random_state,
        ),
        **kwargs,
    )
    print(
        json.dumps(
            {
                "model_path": str(result.model_path),
                "metrics_path": str(result.metrics_path),
                "metrics": result.metrics,
                "best_params": result.best_params,
                "warnings": result.warnings,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
