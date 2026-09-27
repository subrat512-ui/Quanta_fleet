# Current Project Handoff

## Status

- Current phase: Phase 0 — Foundation
- State: Phase 0 implementation and review gates passed; commit and push pending
- Last completed phase: none
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
- Feature commit: pending
- GitHub push: pending
- Pushed commit SHA: not available

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
to later phases. Phase 1 may start only after the Phase 0 commit is pushed.

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
