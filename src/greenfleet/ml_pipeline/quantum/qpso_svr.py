"""Quantum-behaved particle swarm optimization for an RBF SVR.

The optimizer is quantum-inspired and runs on classical hardware.  Particles
search in log10 space for the SVR C, gamma, and epsilon parameters.  Candidate
models are evaluated with the same fixed cross-validation folds so fitness
comparisons are reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

import numpy as np


@dataclass(frozen=True)
class QPSOConfig:
    population_size: int = 16
    iterations: int = 25
    beta_start: float = 1.0
    beta_end: float = 0.5
    random_state: int = 42
    # Bounds are log10(C), log10(gamma), and log10(epsilon).
    bounds: tuple[tuple[float, float], ...] = (
        (-2.0, 4.0),
        (-4.0, 1.0),
        (-4.0, 0.0),
    )

    def validate(self) -> None:
        if self.population_size < 2:
            raise ValueError("population_size must be at least 2")
        if self.iterations < 1:
            raise ValueError("iterations must be at least 1")
        if not (0.0 < self.beta_end <= self.beta_start):
            raise ValueError("require 0 < beta_end <= beta_start")
        if len(self.bounds) != 3 or any(low >= high for low, high in self.bounds):
            raise ValueError("bounds must contain three increasing (low, high) pairs")


@dataclass(frozen=True)
class QPSOResult:
    best_params: dict[str, float]
    best_score: float
    history: list[dict[str, float]]
    evaluations: int


class QPSOSVRTuner:
    """Minimize an externally supplied validation loss using QPSO."""

    def __init__(self, config: QPSOConfig | None = None):
        self.config = config or QPSOConfig()
        self.config.validate()

    @staticmethod
    def decode(position: Sequence[float]) -> dict[str, float]:
        values = np.power(10.0, np.asarray(position, dtype=float))
        return {
            "C": float(values[0]),
            "gamma": float(values[1]),
            "epsilon": float(values[2]),
        }

    def optimize(
        self,
        objective: Callable[[dict[str, float]], float],
    ) -> QPSOResult:
        """Run QPSO and return the parameters with the lowest loss."""
        cfg = self.config
        rng = np.random.default_rng(cfg.random_state)
        lower = np.asarray([item[0] for item in cfg.bounds], dtype=float)
        upper = np.asarray([item[1] for item in cfg.bounds], dtype=float)
        positions = rng.uniform(lower, upper, size=(cfg.population_size, 3))

        def evaluate(population: np.ndarray) -> np.ndarray:
            return np.asarray(
                [float(objective(self.decode(particle))) for particle in population],
                dtype=float,
            )

        scores = evaluate(positions)
        if not np.all(np.isfinite(scores)):
            raise ValueError("objective returned a non-finite loss")

        personal_best = positions.copy()
        personal_scores = scores.copy()
        global_index = int(np.argmin(personal_scores))
        global_best = personal_best[global_index].copy()
        global_score = float(personal_scores[global_index])
        history: list[dict[str, float]] = []

        for iteration in range(cfg.iterations):
            progress = iteration / max(cfg.iterations - 1, 1)
            beta = cfg.beta_start + progress * (cfg.beta_end - cfg.beta_start)
            mean_best = personal_best.mean(axis=0)

            phi = rng.random(size=positions.shape)
            attractor = phi * personal_best + (1.0 - phi) * global_best
            u = np.clip(rng.random(size=positions.shape), np.finfo(float).tiny, 1.0)
            direction = rng.choice(np.asarray([-1.0, 1.0]), size=positions.shape)
            positions = attractor + (
                direction
                * beta
                * np.abs(mean_best - positions)
                * np.log(1.0 / u)
            )
            positions = np.clip(positions, lower, upper)
            scores = evaluate(positions)

            improved = scores < personal_scores
            personal_best[improved] = positions[improved]
            personal_scores[improved] = scores[improved]
            global_index = int(np.argmin(personal_scores))
            if personal_scores[global_index] < global_score:
                global_best = personal_best[global_index].copy()
                global_score = float(personal_scores[global_index])

            decoded = self.decode(global_best)
            history.append(
                {
                    "iteration": float(iteration + 1),
                    "best_cv_mae": global_score,
                    "beta": float(beta),
                    **decoded,
                }
            )

        return QPSOResult(
            best_params=self.decode(global_best),
            best_score=global_score,
            history=history,
            evaluations=cfg.population_size * (cfg.iterations + 1),
        )
