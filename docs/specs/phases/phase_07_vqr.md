# Phase 7 — Variational Quantum Regressor

## Objective

Train a genuine variational quantum circuit regression prototype on a simulator.

## Requirements

- Consume shared row identities and raw feature contract.
- Use six inputs/qubits unless an approved decision changes encoding.
- Fit angle and target scalers on training data only.
- Use a shallow feature map/ansatz and deterministic representative sample.
- The saved Phase 4 six-angle input and target scalers are already fitted on
  training rows; reuse them without fitting in Phase 7. Wind direction stays a
  direct periodic radian angle, while five continuous fields are in `[0, pi]`.
- Initial circuit: one `RY` input rotation per qubit, one linear-CX
  `real_amplitudes` repetition with 12 weights, and mean single-qubit Z
  observable. Execute with exact `QMLEstimator` statevector simulation.
- Train the official prototype with deterministic initial weights and COBYLA
  on scaled-target squared error. Compare ansatz repetitions 1/2 and
  COBYLA/SPSA only in tiny synthetic simulator smoke tests; do not turn that
  comparison into a validation-driven model search.
- Bound training observations and optimizer iterations.
- Quick mode samples 60 time-spaced training rows and uses 14 COBYLA
  evaluations (SciPy's minimum with 12 weights). Normal mode samples 600 rows
  and uses 80 evaluations. Both score every saved validation row, after inverse
  scaling to kg/s. Quick output is smoke evidence, normal is the VQR candidate.
- Persist circuit description, weights, scalers, optimizer and versions.
- Label as `quantum`, backend `simulator`.

## Tests

Use a tiny circuit/sample smoke test guarded by
`GREENFLEET_RUN_QUANTUM_SMOKE=1`. Verify fit, prediction, inverse scaling,
reconstruction, all saved validation identities, absence of validation/test
fitting, and no test-file access. Ordinary offline tests skip quantum execution.

## Gate

Before editing, enter Plan mode and persist circuit, optimizer, sample,
dependency and artifact choices. After simulator tests and independent review
PASS, commit as `feat(quantum): add simulator-based VQR`, push and record the
SHA.

VQR produces finite predictions through the common evaluator and its limitations
are recorded.
