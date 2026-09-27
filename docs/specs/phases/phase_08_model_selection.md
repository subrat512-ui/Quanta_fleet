# Phase 8 — Unified Evaluation and Champion Selection

## Objective

Compare completed candidates fairly and publish one champion artifact.

## Requirements

- One evaluator for all model families.
- Report validation MAE/RMSE/R² and per-vessel validation metrics.
- Select champion using validation MAE only.
- Freeze champion identity and hyperparameters.
- Optionally refit under an explicit, recorded policy.
- Evaluate once on untouched test rows.
- Report overall/per-vessel test metrics and timing.
- Save final model, preprocessing, schema, manifest, metrics and leaderboard.

## Tests

Verify ranking direction, no test-driven selection, family adapters, manifest
completeness and fresh-process inference.

## Gate

Before editing, enter Plan mode and persist the no-leakage evaluation/refit
plan. After independent test/review PASS, commit as
`feat(ml): add champion selection and final artifact`, push and record the
SHA.

One loadable artifact reproduces a prediction and every leaderboard entry has
honest family/backend metadata.
