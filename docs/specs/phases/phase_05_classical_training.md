# Phase 5 — Classical Hyperparameter Tuning

## Objective

Tune and evaluate Ridge, Random Forest, Gradient Boosting and XGBoost.

## Requirements

- Consume Phase 4 artifacts only.
- Use bounded Ridge grid and randomized ensemble searches.
- Use the fixed validation partition through `PredefinedSplit` or equivalent.
- Optimize validation MAE.
- Fix seeds and record search spaces, budgets and dependency versions.
- Save every candidate model, best parameters, validation metrics and metadata.
- Create a classical leaderboard without test metrics.

## Tests

Verify expected candidate count, deterministic small searches, correct objective,
no test access and artifact reload.

## Gate

Before editing, enter Plan mode and persist search budgets, interfaces and tests.
After independent test/review PASS, commit as
`feat(ml): add tuned classical regressors`, push and record the SHA.

All four candidates have comparable validation results and loadable artifacts.
