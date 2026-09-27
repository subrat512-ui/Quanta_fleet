# Phase 7 — Variational Quantum Regressor

## Objective

Train a genuine variational quantum circuit regression prototype on a simulator.

## Requirements

- Consume shared row identities and raw feature contract.
- Use six inputs/qubits unless an approved decision changes encoding.
- Fit angle and target scalers on training data only.
- Use a shallow feature map/ansatz and deterministic representative sample.
- Compare small choices: ansatz repetitions 1/2 and COBYLA/SPSA.
- Bound training observations and optimizer iterations.
- Persist circuit description, weights, scalers, optimizer and versions.
- Label as `quantum`, backend `simulator`.

## Tests

Use a tiny circuit/sample smoke test. Verify fit, predict, inverse scaling,
serialization and absence of validation/test fitting.

## Gate

Before editing, enter Plan mode and persist circuit, optimizer, sample,
dependency and artifact choices. After simulator tests and independent review
PASS, commit as `feat(quantum): add simulator-based VQR`, push and record the
SHA.

VQR produces finite predictions through the common evaluator and its limitations
are recorded.
