# Current Project Handoff

## Status

- Current phase: Phase 3 — MongoDB loading (offline gate complete)
- State: implementation, offline validation, and independent read-only review
  complete; authorized read-only preflight and commit gate pending
- Last completed phase: Phase 2 — FuelCast ETL
- Current branch: `feat/fuelcast-e2e-clean`

The phase records below describe the original branch. The clean recovery
branch excludes its tracked environment and runtime-output deletions and the
unrelated `classical training algorithm` commit. The original branch and its
commit IDs remain intact.

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
- Phase 2 entry conditions were met; the ETL implementation is described below.
- Phase 1 commit: `5336068` (`feat(data): add FuelCast source ingestion`).
  Pushed to `origin/feat/fuelcast-e2e-pipeline` on 2026-09-28. This SHA update
  was written after the push and remains local for the next scoped documentation
  commit.

## Phase 2 handoff

- New API: `run_fuelcast_etl(run_dir: Path) -> FuelCastETLArtifact` in
  `greenfleet.pipeline.etl.fuelcast`; CLI:
  `python -m greenfleet.pipeline.etl.fuelcast --run-id NAME`.
- Source manifest and snapshot are validated before transformation. The stage
  writes the approved 11-column canonical CSV and reconciled audit, preserving
  missing features and dropping invalid targets/times. Exact raw duplicates
  are counted; conflicting vessel/time keys fail. Each vessel must retain at
  least one valid row. The legacy ETL command and behavior remain separate.
- The `02_etl` path is an atomic symlink to a complete hidden backing directory
  within the run. Rollback/removal of local output must remove both paths.
- Selected run: `fuelcast-phase1-20260928-002`, revision
  `eb6a6ec011c1c9a2cbce21459e22be4c77ef84dd`. Canonical counts:
  105,422 Poseidon; 25,347 Triton; 43,205 Ceto; 173,974 total. Twelve missing
  time indexes were dropped; no target or duplicate rows were dropped.
- Focused tests 10/10; full offline suite 26/26; both ETL help commands,
  output invariants, byte reproduction, Git ignore and diff check passed.
  Independent read-only test and reviewer gates: PASS.
- Phase 3 entry: read its spec and prepare a fresh approved plan. The existing
  MongoDB contains previously merged synthetic data; do not treat it as the
  FuelCast canonical load. No MongoDB state was changed in Phase 2.
- Phase 2 replay commit: `50dd953` on `feat/fuelcast-e2e-clean`; pushed.

## Phase 3 checkpoint — 2026-09-28

- The approved detailed plan is persisted in
  `docs/plans/fuelcast_e2e_implementation.md`; Phase 3 is `in_progress`.
- Work completed: FuelCast MongoDB defaults/index definitions, package
  exports, result artifact, specialized preflight/load/report CLI module,
  mocked tests, guarded integration test, and README guidance. The loader
  validates immutable CSV/audit bytes before connection, performs read-only
  preflight, reuses equivalent indexes, uses unordered `UpdateOne`/
  `$setOnInsert`, verifies post-state, and writes a sanitized atomic report.
  Partial bulk-write numeric progress is recorded without driver error text.
- Modified/created implementation files:
  `src/greenfleet/constants/fuelcast.py`,
  `src/greenfleet/database/__init__.py`,
  `src/greenfleet/artifacts/fuelcast_mongodb_artifact.py`,
  `src/greenfleet/database/fuelcast.py`, `tests/test_fuelcast_mongodb.py`,
  `tests/test_fuelcast_mongodb_integration.py`, and `README.md`.
- Checkpoint documentation also modifies this handoff, the implementation
  plan, and `docs/specs/phases/phase_03_mongodb.md`.
- Offline validation: focused suite 22 total (21 pass, 1 guarded live skip);
  full suite 48 total (47 pass, 1 skip); both database help commands and
  `git diff --check` pass. PyMongo 4.18.0 and the authoritative local Phase 2
  inputs are available.
- Independent read-only code review: PASS, no blocker/major findings; minor
  cleanup applied. Independent offline test execution: PASS. The test reviewer
  flagged the active phase spec's orchestration sentence and destination-report
  safety edge. The approved plan assigns standalone persistence to Phase 3
  and orchestrator wiring to Phase 9; destination names now validate and
  failed reports redact invalid values.
- Authorized read-only preflight of run `fuelcast-phase1-20260928-002`: PASS.
  Canonical SHA-256
  `262428b4b2002435806f60aa9939755798dc9fe208b0c4b5d963a9200639cc65`;
  audit SHA-256
  `0f48b7a862703d7cf365d8299b0e32aad626866a963008ce39b12a4953fd264e`;
  dataset version `eb6a6ec011c1c9a2cbce21459e22be4c77ef84dd`.
  Counts: Poseidon 105,422; Triton 25,347; Ceto 43,205; total 173,974.
  `greenfleet.fuelcast_telemetry` was absent, with zero documents,
  active-version rows, conflicts, and unsafe keys. All three indexes remain
  to create: `fuelcast_record_id_unique`, `fuelcast_dataset_version`, and
  `fuelcast_vessel_time`. `safe_to_apply` was true; no database state changed.
- Final gate: focused tests 21 total (20 passed, one guarded integration skip);
  full offline suite 48 total (47 passed, one guarded integration skip); both
  database help commands, `git diff --check`, and independent final code review
  passed with no blocker or major findings. The opt-in live integration test
  remains unrun by design. `--apply` was not run. The legacy generic loader and
  `python -m greenfleet.database SOURCE` remain unchanged.
- Phase 3 commit `1f9705d2dab8006a2c764edde84adbc465949d5e` was pushed to
  `origin/feat/fuelcast-e2e-clean`. Phase 3 is complete; Phase 4 is next.

## Clean branch recovery

- Base: `origin/main` at `026572d`. Original commits `1fdb30d`, `5336068`
  and `c4235e2` remain on `feat/fuelcast-e2e-pipeline`.
- Scoped replay commits: Phase 0 `9f527bb`, Phase 1 `dff071a`, and Phase 2
  `50dd953`. Phase 0 also carries the two transformation path constants needed
  by the baseline model-training config, without importing the classical
  trainer commit.
- Comparison with `origin/main`: 33 files. No `.greenfleet/`, `artifacts/`,
  `greenfleet.egg-info/` or `artifacts.zip` changes. The sole deleted file is
  the superseded `pipeline2.py`.
- Full offline suite: 26/26 passed in the separate worktree. The original
  worktree's uncommitted files remain untouched.
- The clean branch was pushed to `origin/feat/fuelcast-e2e-clean`; draft
  replacement PR #3 is open. Oversized PR #2 and its branch remain unchanged.

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
