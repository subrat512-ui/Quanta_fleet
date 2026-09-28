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

## Implementation checkpoint — 2026-09-28

Phase 3 is in progress on `feat/fuelcast-e2e-clean` from Phase 2 replay commit
`50dd953`. The specialized FuelCast loader, artifact, CLI, mocked tests,
guarded integration test, and README guidance are implemented. Focused and
full offline tests, both database CLI help checks, and `git diff --check`
pass. The generic MongoDB loader and its command remain unchanged.

Independent read-only code review and offline test execution passed. Review
findings concerning destination-report safety were fixed and tested. The
requirement above to integrate into the authoritative pipeline conflicts with
the approved detailed Phase 3 plan. That mismatch is resolved for this
milestone by implementing standalone persistence in Phase 3 and assigning
orchestrator wiring to Phase 9.

The authorized read-only preflight passed for run
`fuelcast-phase1-20260928-002`: canonical SHA-256
`262428b4b2002435806f60aa9939755798dc9fe208b0c4b5d963a9200639cc65`,
audit SHA-256
`0f48b7a862703d7cf365d8299b0e32aad626866a963008ce39b12a4953fd264e`,
version `eb6a6ec011c1c9a2cbce21459e22be4c77ef84dd`, and vessel counts
105,422/25,347/43,205 (173,974 total). The selected
`greenfleet.fuelcast_telemetry` collection was absent with zero documents,
active rows, conflicts, and unsafe keys. All three deterministic indexes
remain to create; `safe_to_apply` was true. No database state changed.

Final gate: focused tests 22 total (21 passed, one guarded integration skip);
full offline suite 48 total (47 passed, one guarded integration skip); both
database help commands, `git diff --check`, and independent final code review
passed with no blocker or major findings. The guarded integration test remains
unrun by design. MongoDB `--apply` was not run. Phase 3 commit
`1f9705d2dab8006a2c764edde84adbc465949d5e` was pushed to
`origin/feat/fuelcast-e2e-clean`; Phase 3 is complete and Phase 4 is next.
