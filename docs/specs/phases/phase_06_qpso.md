# Phase 6 — Quantum-Inspired QPSO-SVR

## Objective

Use QPSO to tune a classical RBF-SVR under the shared data contract.

## Requirements

- Optimize `C`, `gamma`, `epsilon` against validation MAE.
- Do not create another random split.
- Deterministically time-sample at most 4,000 training rows per vessel initially.
- Quick defaults: population 6, iterations 5.
- Record bounds, seed, history, full/sample counts and timing.
- Save model and validation artifacts.
- Label as `quantum_inspired` and `classical` hardware.

## Tests

Use a tiny search. Verify determinism, bound enforcement, shared validation,
history serialization and honest model metadata.

## Gate

Before editing, enter Plan mode and persist QPSO bounds, sampling, artifacts and
tests. After independent test/review PASS, commit as
`feat(quantum): add QPSO-tuned SVR`, push and record the SHA.

The candidate predicts through the shared interface and enters the leaderboard
without any claim of quantum-hardware execution.
