# Phase 4 — Chronological Split and Preprocessing

## Objective

Create the single saved data contract consumed by every model family.

## Requirements

- Split each vessel chronologically 70/15/15.
- Persist exact row IDs and time boundaries.
- Assert strict temporal ordering per vessel.
- Fit median imputation on training only.
- Convert wind direction to sine/cosine.
- Fit standard scaling on training only.
- Provide separate VQR angle and target scaling interfaces.
- Preserve vessel/row identity for metrics.
- Save train, validation, test, preprocessor, schema and manifest artifacts.

## Tests

Verify deterministic boundaries, no overlap, no future-statistic leakage,
correct circular encoding and transform/load consistency.

## Gate

Before editing, enter Plan mode and persist the approved transformation plan.
After leakage tests and independent review PASS, commit as
`feat(ml): add chronological splitting and preprocessing`, push and record the
SHA.

All candidates can load identical partitions and no validation/test information
affects fitted preprocessing.
