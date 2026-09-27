# Current Project Handoff

## Status

- Current phase: Phase 2 — FuelCast ETL (not started)
- State: Phase 1 implementation, offline tests, live source check and independent reviews passed; scoped commit and push pending
- Last completed phase: Phase 1 — FuelCast ingestion
- Current branch: `feat/fuelcast-e2e-pipeline`

## Approved scope

FuelCast ingestion, ETL, MongoDB persistence, chronological transformation,
tuned classical models, QPSO-SVR, VQR, unified evaluation and champion artifact.

## Stable contracts

- Dataset: `krohnedigital/FuelCast`
- Configurations: `cps_poseidon`, `cps_triton`, `oss_ceto`
- Target: `fuel_consumption_kg_s`
- Split: per-vessel chronological 70/15/15
- Selection: validation MAE
- Test: untouched until champion is frozen

## Phase 0 objective

Repair repository foundations and choose one authoritative ML orchestrator.
Do not implement FuelCast ingestion or model training yet.

## Required workflow state

- Phase specification read: done
- Read-only planning inspection: done
- Approved plan persisted: done
- Implementation: done
- Focused tests: 3/3 passed
- Full offline tests: 11/11 passed using `.greenfleet/bin/python`
- Test-agent result: PASS
- Reviewer result: PASS
- Feature commit: `1fdb30d` (`chore(pipeline): repair training foundation`)
- GitHub push: passed to `origin/feat/fuelcast-e2e-pipeline`
- Pushed commit SHA: `1fdb30d`

## Phase 0 work completed

- `pipeline.py` is the single legacy ML orchestrator; incompatible
  `pipeline2.py` was removed. `--help` runs without starting data stages.
- Source artifact classes are included in Git. The ignore rules cover generated
  directories and root runtime artifacts. Previously tracked environment,
  package metadata and two runtime output files were removed from the Git
  index while remaining on the local filesystem.
- The supplied specification package is available under the expected `docs/`
  paths; its original untracked location is left untouched.
- Root resolution and transformation constants were checked and already
  correct. The system Python baseline lacks the installed package and
  `pymongo`; the project environment passes the full offline test suite.

FuelCast schema migration, chronological splits and training remain assigned
to later phases. Phase 1 has not started. Its entry conditions are satisfied:
the Phase 0 commit is pushed, the docs are in their authoritative paths, and
the next agent must perform a fresh read-only Phase 1 spec-to-plan pass.

The SHA update was written locally after the Phase 0 push. It is intentionally
not a second Phase 0 commit and should be carried in the next scoped
documentation commit.

## Phase 1 handoff

- New source API: `ingest_fuelcast(run_dir: Path, revision: str | None = None)`
  returns `FuelCastSourceArtifact` with paths, resolved Hub SHA and row counts.
  CLI: `python -m greenfleet.data_sources --run-id NAME [--revision REV]`.
- Raw output has `vessel_id`, `time_index` and the seven approved FuelCast
  source fields; no target filtering, imputation or canonical renaming occurs.
- Manifest records provenance, schema fingerprints, counts and snapshot hash.
  A complete snapshot and manifest publish only after all three loads pass.
- Focused tests: 5/5; full offline suite: 16/16. CLI help, diff check and
  independent read-only test/reviewer gates passed.
- Live pinned revision: `eb6a6ec011c1c9a2cbce21459e22be4c77ef84dd`.
  Counts: `cps_poseidon` 105,422; `cps_triton` 25,351; `oss_ceto` 43,213;
  total 173,986. CSV counts and SHA-256 were verified against the manifest.
  Generated files are ignored; do not commit or redistribute them.
- Phase 2 entry: read its spec, make a fresh approved plan, consume this raw
  snapshot contract, and implement canonical ETL with row-level audit. No
  Phase 2 implementation has begun.
- Phase 1 commit and push: pending final staged-diff gate.

## Required Phase 0 evidence

- baseline import/test output;
- orchestration call graph;
- list of missing or ignored artifact modules;
- path/constants defects;
- exact allowed change set;
- focused validation commands.

## Known risks

- competing pipeline modules;
- source artifact files hidden by a broad ignore pattern;
- undefined transformation constants;
- project root resolving incorrectly;
- existing random splits and test-based model selection.

## Update rule

After a phase gate passes, replace this file with:

- completed phase and evidence;
- new current phase;
- authoritative artifacts created;
- interface changes;
- unresolved risks;
- exact next-phase entry conditions.
- pushed commit SHA and branch.
