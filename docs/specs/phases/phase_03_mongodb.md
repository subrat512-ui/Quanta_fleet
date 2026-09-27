# Phase 3 — MongoDB Load

## Objective

Persist the canonical dataset idempotently and verify the active version.

## Requirements

- Database `greenfleet`, collection `fuelcast_telemetry`.
- Batch upsert by `record_id`.
- Create required unique, version and vessel/time indexes.
- Convert missing feature values safely to MongoDB nulls.
- Verify counts scoped to `dataset_version`.
- Persist load report without secrets.
- Integrate the stage into the authoritative pipeline.

## Tests

Mock ordinary tests. Verify reruns do not duplicate documents, index requests
are correct, failures are reported and credentials never enter logs.

## Gate

Before editing, enter Plan mode and persist the approved MongoDB plan. After
unit tests, authorized integration checks and independent review PASS, commit as
`feat(database): add idempotent FuelCast MongoDB loading`, push and record the
SHA.

First and repeated loads produce the expected count with no duplicates.
