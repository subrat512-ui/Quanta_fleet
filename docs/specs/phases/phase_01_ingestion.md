# Phase 1 — FuelCast Ingestion

## Objective

Import and normalize all three FuelCast configurations into one raw snapshot.

## Requirements

- Dataset ID: `krohnedigital/FuelCast`.
- Verify `cps_poseidon`, `cps_triton`, `oss_ceto`.
- Load each configuration's `train` split.
- Validate required columns per configuration.
- Add `vessel_id`; rename `index` to `time_index`.
- Retain only approved source fields.
- Save combined raw snapshot and source manifest.
- Record dataset revision/fingerprint, retrieval time and per-vessel rows.

## Tests

Use three small local synthetic fixtures. Test missing config, missing column,
ordering and manifest determinism. Normal tests make no network requests.

## Gate

Before editing, enter Plan mode and persist the approved ingestion plan. After
independent test/review PASS, commit as
`feat(data): add FuelCast source ingestion`, push and record the SHA.

All configurations normalize to one raw schema with correct vessel identity,
row counts and provenance.
