# Phase 0 — Repository Foundation

## Objective

Make a fresh clone importable and establish one authoritative orchestration path.

## Requirements

- Inspect both ML orchestrators and select one.
- Deprecate/remove the incompatible path without unrelated redesign.
- Change broad `artifacts/` ignore behavior to root-only `/artifacts/`.
- Ensure source artifact classes are tracked.
- Ignore generated `.greenfleet/` and `greenfleet.egg-info/`.
- Fix undefined constants and project-root/path defects.
- Capture baseline and final focused test results.

## Allowed scope

`.gitignore`, ML orchestration/config/constants/artifact modules, affected
tests and narrowly related documentation.

## Out of scope

FuelCast download, schema mapping, MongoDB changes and model training.

## Gate

Before editing, enter Plan mode and persist the approved Phase 0 file/change/test
plan. After independent test/review PASS, commit as
`chore(pipeline): repair training foundation`, push the feature branch and
record the SHA before Phase 1.

- `python -c "import greenfleet"` succeeds.
- Existing focused tests pass or pre-existing failures are documented.
- One orchestrator is authoritative.
- A fresh clone contains required source modules.
