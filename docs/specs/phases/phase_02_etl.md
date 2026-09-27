# Phase 2 — Canonical ETL

## Objective

Produce the canonical FuelCast dataset and a complete cleaning audit.

## Requirements

- Apply the master source-to-canonical map.
- Coerce numeric fields and replace infinities.
- Drop and audit invalid targets; never impute target.
- Preserve missing features.
- Remove and audit exact duplicates.
- Require unique vessel/time pairs.
- Generate deterministic `record_id` and `dataset_version`.
- Sort by vessel and time.
- Save `fuelcast_clean.csv` and `etl_audit.json`.

## Tests

Cover invalid target variants, feature null preservation, duplicate handling,
stable identifiers, ordering and schema failure.

## Gate

Before editing, enter Plan mode and persist the approved ETL plan. After
independent test/review PASS, commit as
`feat(etl): add canonical FuelCast transformation`, push and record the SHA.

Canonical output matches the approved schema and is byte/logically reproducible
for the same source version and configuration.
