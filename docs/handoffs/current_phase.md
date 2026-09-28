# Current Project Handoff

## Status

- Current phase: Phase 7 — VQR planning
- State: Phase 5 classical tuning is complete on
  `feat/fuelcast-classical-models`; its review and validation gates passed.
  Phase 6 QPSO-SVR remains deferred; VQR requires a fresh approved plan before
  implementation.
- Last completed phase: Phase 5 — bounded classical regression tuning
- Current branch: `feat/fuelcast-classical-models`

Phase 5 reads only saved Phase 4 training and validation partitions from an
explicit run directory. Quick and normal searches have separate output
directories under `05_classical`. Neither is a production champion; later
selection across approved families remains validation-MAE based. QPSO-SVR is
deferred from the current MVP roadmap, with its specification retained.

One transient three-byte whitespace edit to the Phase 4 feature schema caused
the loader's hash check to reject an in-progress real normal run. The altered
bytes were backed up under `/private/tmp` and the original schema bytes were
restored to their manifest hash before reruns. No data arrays changed.

Both real Phase 5 modes completed and published four candidates each. Quick
validation MAE ranking: Random Forest 0.122604, Gradient Boosting 0.143913,
XGBoost 0.146567, Ridge 0.295065. Normal validation MAE ranking: XGBoost
0.120164, Random Forest 0.120935, Gradient Boosting 0.131695, Ridge 0.248201.
Each model passed fresh-process reload before its mode was published. These
generated results are ignored, validation-only artifacts; there is no final
champion or test score at this phase.
Focused synthetic tests: 9/9 passed. Full offline suite: 66 tests, one opt-in
integration skip. CLI help, explicit normal Ridge reload, `git diff --check`
and independent read-only reviews passed. The classical leaderboard is
validation-only and does not select the final production champion. No test
evaluation was run.

The phase records below describe the original branch. The clean recovery
branch excludes its tracked environment and runtime-output deletions and the
unrelated `classical training algorithm` commit. The original branch and its
commit IDs remain intact. Earlier checkpoint statements are historical; use
the current status above and `docs/SESSION_HANDOFF.md` for the latest state.

## Approved scope

FuelCast ingestion, ETL, MongoDB persistence, chronological transformation,
tuned classical models, VQR, unified evaluation and champion artifact.
QPSO-SVR is deferred from the immediate MVP roadmap; its specification remains.

## Stable contracts

- Dataset: `krohnedigital/FuelCast`
- Configurations: `cps_poseidon`, `cps_triton`, `oss_ceto`
- Target: `fuel_consumption_kg_s`
- Split: per-vessel chronological 70/15/15
- Selection: validation MAE
- Test: untouched until champion is frozen

## Phase 4 implementation checkpoint

- New API: `run_fuelcast_transformation(run_dir: Path)` and
  `load_fuelcast_partitions(run_dir: Path)` in
  `greenfleet.ml_pipeline.transformation.fuelcast`; CLI uses `--run-dir`.
- The stage verifies the immutable Phase 2 CSV and audit, creates per-vessel
  chronological 70/15/15 partitions, and saves exact IDs/time boundaries,
  aligned classical/VQR arrays and training-fitted preprocessors.
- The pinned canonical run produced 121,780 train, 26,096 validation and
  26,098 test rows (173,974 total). Its source SHA-256 and version match the
  Phase 3 handoff. Generated `04_transformation` remains ignored.
- Focused tests 9/9; full offline suite 57 total (56 passed, one guarded
  MongoDB integration skip); CLI help and diff check passed. Independent
  read-only test and code reviews: PASS, with the circular wind finding fixed.
- Phase 4 commit `1c8e93365c16823e2756c3b649d5af4ead236d30`
  (`feat(ml): add chronological splitting and preprocessing`) was pushed to
  `origin/feat/fuelcast-e2e-clean` on 2026-09-28.
- Phase 5 classical training is next; start with its spec-to-plan cycle.

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
- Final gate: focused tests 22 total (21 passed, one guarded integration skip);
  full offline suite 48 total (47 passed, one guarded integration skip); both
  database help commands, `git diff --check`, and independent final code review
  passed with no blocker or major findings. The opt-in live integration test
  remains unrun by design. At that implementation gate, `--apply` had not yet
  run; the subsequent production load is recorded below. The legacy generic
  loader and `python -m greenfleet.database SOURCE` remain unchanged.
- Phase 3 commit `1f9705d2dab8006a2c764edde84adbc465949d5e` was pushed to
  `origin/feat/fuelcast-e2e-clean`. Phase 3 is complete; Phase 4 is next.

## Phase 3 production load and Phase 4 entry

The existing Phase 3 `--apply` path loaded the immutable canonical source
`artifacts/fuelcast-phase1-20260928-002/02_etl/fuelcast_clean.csv` into
**`greenfleet.fuelcast_telemetry`**. The canonical version is
`eb6a6ec011c1c9a2cbce21459e22be4c77ef84dd`, with 173,974 rows and CSV
SHA-256 `262428b4b2002435806f60aa9939755798dc9fe208b0c4b5d963a9200639cc65`.
The generated report is
`artifacts/fuelcast-phase1-20260928-002/03_mongodb/mongodb_load_report.json`.

First load: 173,974 attempted, 173,974 inserted, 0 skipped/existing, and 0
modified. Post-load verification: collection and active-version counts both
173,974; every canonical ID present; zero canonical-content conflicts,
duplicate `record_id` values, duplicate active-version vessel/time keys, or
extra active-version IDs; all three required indexes verified. The follow-up
read-only preflight recognized all 173,974 records as existing, found zero
conflicts and zero indexes to create, and implies 0 new inserts on a subsequent
idempotent load. No second write was run.

Preserve all legacy MongoDB collections and data. Phase 4 must use this
canonical FuelCast CSV and version, never the old merged synthetic dataset.
It must not train by querying mutable MongoDB state. The exact Phase 4
objective is “Create the single saved data contract consumed by every model
family.” Phase 4 has not begun; start with the fresh spec-to-plan cycle in
`docs/specs/phases/phase_04_transformation.md`. See `docs/SESSION_HANDOFF.md`
for the complete fresh-session reading list, subagent workflow, commits, and
remaining assumptions.

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
