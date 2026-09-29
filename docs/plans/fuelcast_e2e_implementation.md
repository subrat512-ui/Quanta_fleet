# FuelCast End-to-End Implementation Plan

Current feature branch: `feat/fuelcast-model-selection`. Earlier references
to `feat/fuelcast-e2e-clean` and `feat/fuelcast-e2e-pipeline` describe prior
phase worktrees. See `docs/SESSION_HANDOFF.md` for the latest operational
state and handoff.

## Status legend

- `pending`: not started
- `in_progress`: active phase
- `blocked`: cannot continue without a decision
- `passed`: implemented and phase gate accepted
- `deferred`: retained in the specification, outside the current MVP sequence

| Phase | Name | Status | Depends on |
| --- | --- | --- | --- |
| 0 | Foundation | passed | none |
| 1 | FuelCast ingestion | passed | 0 |
| 2 | ETL | passed | 1 |
| 3 | MongoDB | passed | 2 |
| 4 | Split and preprocessing | passed | 2, 3 |
| 5 | Classical tuning | passed | 4 |
| 6 | QPSO-SVR | deferred | 4 |
| 7 | VQR | passed and pushed | 4 |
| 8 | Model selection | passed, push pending | 5, 7 |
| 9 | Orchestration | pending | 3, 8 |

## Phase execution protocol

Every phase starts with a fresh spec-to-plan cycle:

1. Read the master spec, decisions, handoff and active phase spec.
2. Enter Plan mode; a read-only explorer maps relevant code and baseline.
3. Produce an exact plan: files, interfaces, migrations, tests, commands,
   risks and rollback considerations.
4. Approve and persist that phase plan here before editing.
5. One implementation agent edits only approved files.
6. Run focused tests and `git diff --check`.
7. Independent test and reviewer agents perform the broad phase gate.
8. Fix all blocker/major findings and repeat validation.
9. On PASS, stage only phase-owned changes and create the scoped commit.
10. Push the reviewed phase branch; Phase 7 uses `feat/fuelcast-vqr`.
11. Record commit SHA, commands, test/review result and push state here and in
    the handoff.
12. Begin the next phase only after the push succeeds.

## Feature branch and commit plan

Phase 7 branch: `feat/fuelcast-vqr`, tracking `origin/feat/fuelcast-vqr`.
Earlier phases used
`feat/fuelcast-e2e-clean` and `feat/fuelcast-classical-models`.

| Phase | Commit subject |
| --- | --- |
| 0 | `chore(pipeline): repair training foundation` |
| 1 | `feat(data): add FuelCast source ingestion` |
| 2 | `feat(etl): add canonical FuelCast transformation` |
| 3 | `feat(database): add idempotent FuelCast MongoDB loading` |
| 4 | `feat(ml): add chronological splitting and preprocessing` |
| 5 | `feat(ml): add tuned classical regressors` |
| 6 | `feat(quantum): add QPSO-tuned SVR` |
| 7 | `feat(quantum): add simulator-based VQR` |
| 8 | `feat(ml): add champion selection and final artifact` |
| 9 | `feat(pipeline): add FuelCast end-to-end orchestration` |

Before each commit/push:

```bash
git status --short
git diff --check
git diff
git diff --cached
```

Never use `git add .` blindly. Never push a failing phase, unresolved
blocker/major findings, secrets, datasets, artifacts or unrelated changes.

## Cross-phase rules

- No overlapping writers.
- No raw FuelCast data in Git.
- No external network requirement in ordinary tests.
- No new split created inside a trainer.
- No test-set use during tuning or selection.
- No unsupported quantum claims.

## Approved Phase 8 plan — validation champion and final test

Authorization: the user supplied the exact Phase 8 implementation plan for a
clean worktree at `/private/tmp/fuelcast-phase8`, branch
`feat/fuelcast-model-selection`, based on `origin/main` commit `0c025d7`.
The original worktree remains untouched. This plan fixes refit policy to
`false`; only normal-mode Ridge, Random Forest, Gradient Boosting, XGBoost and
VQR are eligible. QPSO-SVR remains deferred.

- Add `ml_pipeline/evaluation/fuelcast.py`, package exports and a CLI. Read the
  saved Phase 4 train/validation contract, verify the five candidate hashes,
  provenance, ordered validation predictions and recalculated overall and
  per-vessel MAE/RMSE/R². Break exact MAE ties by candidate name.
- Persist `07_evaluation/leaderboard.json` and `selection_manifest.json`, then
  package the selected saved candidate, training-fitted preprocessor and schema
  under `artifacts/final_model`. Record all hashes, versions and selection
  provenance. Reject an existing or conflicting selection.
- Open `test.npz` only in a separate `evaluate` command after the selection and
  final package are frozen. Check the saved hash, array schema, ordered IDs,
  uniqueness, per-vessel boundaries, disjoint identities and finite values.
  Predict with the packaged winner once, publish aligned test predictions,
  overall/per-vessel metrics, and an evaluation manifest. Never select on test.
- Add synthetic tests in `tests/test_fuelcast_model_selection.py`; update README,
  plan, decisions and handoffs. Existing Phase 4/5/7 model and transformation
  contracts and the Phase 9 orchestrator remain unchanged.
- Gate: focused Phase 8 and Phase 4/5/7 tests; full offline suite; CLI help;
  fresh-process inference; `git diff --check`; independent read-only code and
  test review. Then select from pinned run/version/checksum, inspect leaderboard,
  verify fresh-process package, evaluate exactly once and audit 26,098 IDs.
  Commit only Phase 8 files and push the reviewed branch.

Risks: the local macOS XGBoost library needs `libomp.dylib`, supplied here by
the installed scikit-learn runtime through `DYLD_LIBRARY_PATH`. The package
loader must retain dependency/version checks and no-fit inference. Rollback
before final test is limited to removing a newly published, fully inspected
Phase 8 package and selection directory; never modify candidate or split
artifacts. Once test is evaluated, preserve its single authoritative report.

### Phase 8 implementation and verification — 2026-09-29

Added the evaluation package and CLI, plus 11 synthetic tests. Selection verifies
five normal-mode candidates, full aligned validation predictions, recomputed
overall/per-vessel metrics, versions, provenance and hashes. It reconstructs
all VQR validation predictions before ranking. It publishes a frozen no-refit
package and leaderboard without accessing the test array. Evaluation verifies
the frozen package, source and test identities, then stages complete outputs
behind atomic symlinks with an interruption recovery marker. Phase 4/5/7
training files, saved arrays, candidates and Phase 9 orchestrator were unchanged.

- Pinned revision: `eb6a6ec011c1c9a2cbce21459e22be4c77ef84dd`; canonical
  SHA-256: `262428b4b2002435806f60aa9939755798dc9fe208b0c4b5d963a9200639cc65`.
- Validation rank on 26,096 rows: XGBoost MAE 0.12016408036458692, Random
  Forest 0.12093455540592271, Gradient Boosting 0.1316948447165451, Ridge
  0.24820052304262852, VQR 0.2830684142645837 kg/s. Champion: XGBoost.
- The first frozen validation output was removed before test access because
  review found publication/integrity defects. Selection was rerun with the
  corrected format; no split, candidate or test artifact was changed.
- Fresh-process package inference passed before and after final evaluation.
  The one authoritative test on 26,098 rows: MAE 0.12854118081363877,
  RMSE 0.1841633970560541, R² 0.8921833518766525. Per-vessel test MAE:
  Poseidon 0.11105636056362754 (15,814 rows), Triton 0.24624725780310447
  (3,803), Ceto 0.10213611009040768 (6,481), all kg/s.
- `07_evaluation/test_predictions.npz` has 26,098 ordered unique IDs, all
  three vessels. Selection, evaluation and final manifests name XGBoost;
  evaluation and final package hashes verify. Runtime outputs remain ignored.
- Phase 8 focused tests: 11/11 passed. Phase 4/5/7 regression: 29 tests with
  six opt-in quantum skips. Full offline suite: 88 tests, seven opt-in skips.
  CLI help and `git diff --check` passed. Independent read-only code and test
  reviews found no remaining blocker or major code issue after fixes.
- Phase 8 branch: `feat/fuelcast-model-selection` from `origin/main` `0c025d7`.
  Record the pushed scoped feature commit SHA below after the push.

## Approved Phase 7 plan — simulator-based VQR

Authorization: Phase 7 implementation is approved on `feat/fuelcast-vqr`, based
on `origin/main` at `7375e74`. QPSO-SVR remains deferred. The authoritative
run is `fuelcast-phase1-20260928-002`, revision
`eb6a6ec011c1c9a2cbce21459e22be4c77ef84dd`, canonical SHA-256
`262428b4b2002435806f60aa9939755798dc9fe208b0c4b5d963a9200639cc65`.

- Add a VQR-only train/validation loader. Verify run, schema, hashes and saved
  identities without opening or hashing `test.npz`. Reuse the six Phase 4 VQR
  angles and the training-fitted Phase 4 angle and target scalers unchanged.
- Encode one approved input per qubit with `RY`: speed, wind speed, periodic wind
  direction, wave height, wave period and current speed. Use a one-layer
  `real_amplitudes` ansatz with linear CX entanglement (12 weights), observable
  `(Z0+Z1+Z2+Z3+Z4+Z5)/6`, and exact simulator `QMLEstimator`.
- Fit Qiskit Machine Learning `VQR` with scaled-target squared error,
  deterministic seed 42 initial weights, and COBYLA. Quick mode uses 60
  time-spaced training rows (36/9/15 per vessel) and 14 evaluations, the
  SciPy COBYLA minimum for 12 weights. Normal
  mode uses 600 rows (364/87/149) and 80 evaluations. Both modes predict all
  26,096 saved validation rows in batches of 256; quick is smoke-only because
  of its small training budget. Cooperative elapsed-time checks use 600 seconds
  quick and 7,200 seconds normal for fitting, plus a separate 3,600-second
  validation budget. Each check runs after an objective call or prediction
  batch; it cannot interrupt a single stalled simulator call.
- Save mode-specific, reconstruction-based candidate artifacts under
  `06_quantum/vqr/<mode>/candidate`, including weights, circuit configuration,
  Phase 4 scaler copies, schema, sample IDs, optimizer history, validation
  predictions and metrics. Reconstruct an `EstimatorQNN` for fresh-process
  inference. Publish a complete mode directory atomically after verification.
- Keep Qiskit dependencies optional and lazy-imported. Declare Qiskit 2.5.2
  and Qiskit Machine Learning 0.9.1 separately; no Aer or Algorithms package
  is required for exact statevector simulation. A guarded synthetic-only smoke
  matrix checks one/two ansatz repetitions and COBYLA/SPSA, while real quick
  and normal execution remain fixed to one repetition and COBYLA. Require the
  tiny simulator gate before any real run.
- Validate deterministic sampling, six-qubit circuit width, training-only
  scaling, metric units, no test-file access, model reconstruction and honest
  labels using synthetic fixtures. Run focused tests, the offline suite and
  `git diff --check`. Independent test and code reviewers must pass before a
  scoped commit and push. The intended commit is
  `feat(quantum): add simulator-based VQR`.

Risk controls: quick mode measures runtime before normal execution; shallow
circuits and 256-row prediction batches limit memory; callback history persists
in unpublished staging output so interruption does not publish a partial
candidate. `--resume-checkpoint ABSOLUTE_STAGING_CANDIDATE` starts a new COBYLA
attempt from that checkpoint's best loss; the optimizer state is reset and both
attempt IDs are recorded. Rollback leaves Phase 4 and Phase 5 artifacts intact
and removes only inspected unpublished Phase 7 output. No production champion
or test evaluation is part of this phase.

Phase 7 entry point and validation commands (from `/private/tmp/fuelcast-vqr`):

```bash
PYTHONPATH=src /Users/subrat/Desktop/SIH/.greenfleet/bin/python -c 'import importlib.metadata as m; print({n: m.version(n) for n in ("qiskit", "qiskit-machine-learning", "numpy", "scipy", "scikit-learn")})'
PYTHONPATH=src /Users/subrat/Desktop/SIH/.greenfleet/bin/python -m unittest discover -s tests -p 'test_fuelcast_vqr.py' -v
GREENFLEET_RUN_QUANTUM_SMOKE=1 PYTHONPATH=src /Users/subrat/Desktop/SIH/.greenfleet/bin/python -m unittest discover -s tests -p 'test_fuelcast_vqr.py' -v
GREENFLEET_RUN_QUANTUM_SMOKE=1 PYTHONPATH=src /Users/subrat/Desktop/SIH/.greenfleet/bin/python -m unittest discover -s tests -p 'test_fuelcast_vqr.py' -k test_synthetic_quick_cli -v
GREENFLEET_RUN_QUANTUM_SMOKE=1 PYTHONPATH=src /Users/subrat/Desktop/SIH/.greenfleet/bin/python -m unittest discover -s tests -p 'test_fuelcast_vqr.py' -k test_fresh_process_reconstruction -v
GREENFLEET_RUN_QUANTUM_SMOKE=1 PYTHONPATH=src /Users/subrat/Desktop/SIH/.greenfleet/bin/python -m unittest discover -s tests -p 'test_fuelcast_vqr.py' -k test_full_trainer_guard_and_checkpoint_restart -v
DYLD_LIBRARY_PATH=/Users/subrat/Desktop/SIH/.greenfleet/lib/python3.11/site-packages/sklearn/.dylibs PYTHONPATH=src /Users/subrat/Desktop/SIH/.greenfleet/bin/python -m unittest discover -s tests -v
git diff --check
```

Opt-in real commands, only after synthetic gates and runtime assessment:

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONPATH=src /Users/subrat/Desktop/SIH/.greenfleet/bin/python -m greenfleet.ml_pipeline.quantum.fuelcast_vqr train --run-dir /Users/subrat/Desktop/SIH/artifacts/fuelcast-phase1-20260928-002 --mode quick --expected-version eb6a6ec011c1c9a2cbce21459e22be4c77ef84dd --expected-canonical-sha256 262428b4b2002435806f60aa9939755798dc9fe208b0c4b5d963a9200639cc65
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONPATH=src /Users/subrat/Desktop/SIH/.greenfleet/bin/python -m greenfleet.ml_pipeline.quantum.fuelcast_vqr train --run-dir /Users/subrat/Desktop/SIH/artifacts/fuelcast-phase1-20260928-002 --mode normal --expected-version eb6a6ec011c1c9a2cbce21459e22be4c77ef84dd --expected-canonical-sha256 262428b4b2002435806f60aa9939755798dc9fe208b0c4b5d963a9200639cc65
PYTHONPATH=src /Users/subrat/Desktop/SIH/.greenfleet/bin/python -m greenfleet.ml_pipeline.quantum.fuelcast_vqr verify --run-dir /Users/subrat/Desktop/SIH/artifacts/fuelcast-phase1-20260928-002 --candidate-dir /Users/subrat/Desktop/SIH/artifacts/fuelcast-phase1-20260928-002/06_quantum/vqr/normal/candidate
```

### Phase 7 implementation gate — 2026-09-29

The quick and normal runs completed against authoritative run
`fuelcast-phase1-20260928-002`. Each scored all 26,096 saved validation rows.
The quick 60-row/14-evaluation smoke run had validation MAE
`0.415270197450664` kg/s, fit time 0.674 s and prediction time 20.136 s.
The normal 600-row/80-evaluation prototype had validation MAE
`0.2830684142645837` kg/s, RMSE `0.3683189258325035` kg/s and R²
`0.5553620947467861`; fit time 37.327 s and prediction time 20.141 s.
Normal per-vessel metrics from the generated candidate manifest:

| Vessel | Rows | MAE (kg/s) | RMSE (kg/s) | R² |
| --- | ---: | ---: | ---: | ---: |
| `cps_poseidon` | 15,813 | 0.282858 | 0.393336 | 0.483275 |
| `cps_triton` | 3,802 | 0.426180 | 0.447769 | -46.900958 |
| `oss_ceto` | 6,481 | 0.199628 | 0.226123 | -2.057488 |

The normal artifact at `06_quantum/vqr/normal/candidate` passed explicit
fresh-process reconstruction and prediction verification. Guarded VQR tests:
11/11 passed; ordinary focused tests: five passed and six quantum tests
skipped; full offline suite: 70 passed, seven opt-in skips with
`DYLD_LIBRARY_PATH`; `git diff --check` and independent code/test reviews:
PASS with no blocker or major findings. Generated outputs remain ignored. The
Phase 7 feature commit `acab7575a37754ed81ea36354377d68b1a82bb10`
(`feat(quantum): add simulator-based VQR`) was pushed to
`origin/feat/fuelcast-vqr` on 2026-09-29. Phase 7 is complete. QPSO-SVR stays
deferred. No test evaluation or production champion selection occurred. Phase 8
requires a fresh specification-to-plan cycle before implementation.

## Approved Phase 4 plan — chronological split and preprocessing

Authorization: the user approved the Phase 4 plan and requested implementation.
Phase 3 is complete on the clean branch at `e8644bf`. The immutable canonical
input is run `fuelcast-phase1-20260928-002`, version
`eb6a6ec011c1c9a2cbce21459e22be4c77ef84dd`, CSV SHA-256
`262428b4b2002435806f60aa9939755798dc9fe208b0c4b5d963a9200639cc65`.

Add `src/greenfleet/ml_pipeline/transformation/fuelcast.py` with
`run_fuelcast_transformation(run_dir: Path) -> FuelCastTransformationArtifact`,
a `--run-dir` CLI and a validated partition loader. Add the artifact class under
`src/greenfleet/artifacts/`. Validate the canonical CSV and Phase 2 audit,
split each vessel at `floor(0.70n)` and `floor(0.85n)`, assert disjoint row IDs
and strict temporal boundaries, and atomically publish `04_transformation`.

Persist aligned train/validation/test NPZ files with classical features, six
VQR angle inputs, original and scaled targets, row IDs, vessel IDs and time
indexes. Fit median imputation for five continuous inputs and circular-mean
imputation for wind direction on training only. Fit classical circular direction
encoding and standard scaling, plus separate training-only VQR angle and target
scaling. Persist all preprocessors, the feature schema
and split manifest. Preserve the legacy random-split API for its callers.

Add `tests/test_fuelcast_transformation.py` for boundaries, identities, audit
integrity, no future-statistic leakage, encoding, scaling, reload and atomic
publication. Update README and handoffs. Mark QPSO-SVR deferred for the current
MVP while retaining its specification; classical and VQR remain the active
comparison. No new dependency or database migration is required.

Run focused and full offline tests, CLI help, `git diff --check` and an
authorized local canonical-run check. Require independent read-only test and
code reviews, fix major findings, inspect the staged diff, then commit as
`feat(ml): add chronological splitting and preprocessing` and push the clean
branch. Rollback is a scoped commit revert and removal of the ignored generated
stage, including its backing directory; the canonical input stays immutable.

### Phase 4 implementation gate

- Focused Phase 4 tests: 9/9 passed. Full offline suite: 57 total, 56 passed,
  one guarded MongoDB integration skip. CLI help and `git diff --check` passed.
- Independent read-only test review: PASS. Independent code review: PASS after
  replacing degree-median wind imputation with a training-fitted circular mean,
  preserving exact int64 time indexes and checking loader vessel/time alignment.
- Pinned canonical run produced 121,780 training, 26,096 validation and 26,098
  test rows, totaling 173,974. Classical arrays have seven columns, VQR arrays
  six. Saved arrays reload, contain finite transformed values and retain the
  canonical hash and version. Generated files remain ignored.
- Scoped staged-diff gate passed. Phase 4 feature commit
  `1c8e93365c16823e2756c3b649d5af4ead236d30` was pushed to
  `origin/feat/fuelcast-e2e-clean` on 2026-09-28. Phase 5 requires a fresh
  spec-to-plan cycle before implementation.

## Approved Phase 3 plan — idempotent FuelCast MongoDB loading

Authorization: the user supplied and approved this Phase 3 plan. Work occurs
only on `feat/fuelcast-e2e-clean` after Phase 2 replay commit `50dd953`. The
authoritative input is run `fuelcast-phase1-20260928-002`, canonical SHA-256
`262428b4b2002435806f60aa9939755798dc9fe208b0c4b5d963a9200639cc65`,
dataset version `eb6a6ec011c1c9a2cbce21459e22be4c77ef84dd`, and 173,974 rows.

### Files and interfaces

- Add `greenfleet.database.fuelcast` with
  `preflight_fuelcast_mongodb(run_dir, *, uri=None, database="greenfleet",
  collection="fuelcast_telemetry")` and `run_fuelcast_mongodb(run_dir, *,
  uri=None, database="greenfleet", collection="fuelcast_telemetry",
  batch_size=1000)`, plus a run-ID CLI whose default mode is read-only
  preflight. The CLI obtains credentials only from `MONGODB_URI`.
- Add `FuelCastMongoPreflight` and a `FuelCastMongoArtifact` carrying report
  path, status, dataset version, expected rows, and verified loaded rows.
- Extend FuelCast constants with destination defaults and deterministic index
  names, and export the FuelCast API without changing the generic loader,
  `vessel_telemetry` default, or `python -m greenfleet.database SOURCE`.
- Add focused mocked unit tests and a guarded, opt-in integration test. Update
  README, this plan, and the current handoff. Do not change Phase 4 or ML code.

### Validation, loading, and verification contract

Capture the canonical CSV and audit as immutable bytes before connecting, then
validate dataset identity, source run, version, hash, ordered schema, counts,
vessels, uniqueness, deterministic IDs, integer times, finite nonnegative
target, and optional finite feature values. Convert only the eleven canonical
fields to explicit BSON-safe Python types, mapping blank features to null.

Preflight is mandatory and read-only. It reports sanitized database,
collection, counts, active-version membership/content, index definitions, and
missing/null/duplicate keys. Conflicting canonical content, extra active-version
IDs, unsafe duplicate keys, or conflicting required index definitions block all
writes. Equivalent indexes are reused; existing indexes are never dropped or
altered.

Apply repeats preflight, creates only missing required indexes, and sends
unordered batches of `UpdateOne({"record_id": ...},
{"$setOnInsert": canonical_document}, upsert=True)`. Post-verification requires
exact active-version total/per-vessel counts and IDs, canonical equality,
unique record and vessel/time keys, and required indexes. Reruns must report
zero upserts and modifications. Every apply attempt atomically replaces a
sanitized `03_mongodb/mongodb_load_report.json`, including safe stage/type
failure metadata but never URIs, addresses, credentials, or raw driver errors.

### Tests, gate, risks, and rollback

Mocked tests cover BSON types/nulls; all source invariant failures before
connection; preflight findings; unrelated state preservation; extra-field
tolerance; conflicts and extra IDs blocking writes; equivalent/conflicting
indexes; exact unordered `$setOnInsert` batches; first, partial, and repeated
loads; every post-verification dimension; partial bulk failure reporting and
safe replay; secret-safe output/reporting; and atomic report replacement.

Run the focused suite, full offline suite, both database help commands, and
`git diff --check`. The integration test runs only with `MONGODB_URI`,
`RUN_FUELCAST_MONGODB_INTEGRATION=1`, and explicit database/collection variables;
the collection must begin `fuelcast_integration_`, uses three synthetic rows,
runs twice, and never deletes data. After offline and independent read-only
review gates pass, run the authoritative read-only preflight and report its
sanitized findings. Do not apply to `greenfleet.fuelcast_telemetry` without a
separate explicit authorization.

Partial unordered writes are recoverable by replay because inserts are
idempotent; no automatic data or index rollback is performed. Concurrent state
changes, permissions, connectivity, or report-write failures are reported
safely and never reconciled by deletion. Code rollback is a revert of the
single scoped Phase 3 commit; database rollback requires a separately
authorized operator procedure.

### Phase 3 checkpoint — 2026-09-28

The approved plan is persisted and Phase 3 remains `in_progress`. The active
phase spec mentions orchestration integration, but the approved Phase 3 plan
defers that work to Phase 9. Implementation now includes FuelCast MongoDB
constants and package exports, the result artifact, source validation,
read-only preflight, safe index comparison, unordered idempotent writes,
post-verification, atomic sanitized reporting, and the dedicated CLI. The
generic loader and command remain unchanged. README guidance and a guarded
three-vessel live integration test are present.

Offline gate evidence:

- focused mocked suite: 22 tests total, 21 pass, 1 guarded integration skip;
- full offline suite: 48 tests total, 47 pass, 1 guarded integration skip;
- FuelCast and generic database `--help` commands: pass;
- `git diff --check`: pass.

These checks cover source hash/schema/count and deterministic IDs, exact
canonical field presence and BSON-safe Python types, index equivalence and
conflict options, sanitized reports, partial bulk-write numeric progress,
replay, each post-verification invariant, CLI secrecy, and atomic report
replacement failure, and BSON int64 bounds before connection. PyMongo 4.18.0
is available. Only synthetic temporary test data was produced; it was removed
by test cleanup.

Independent read-only code review passed with no blocker or major findings;
the review's minor cleanup was applied. Independent offline test execution
passed. The test reviewer identified the active phase spec's orchestration
sentence and a destination-report safety edge. The approved Phase 3 plan
resolves the contract mismatch: this phase implements standalone persistence,
and Phase 9 owns orchestrator wiring. Destination names are now validated
before connection and redacted in failed apply reports, with mocked coverage.

Authorized read-only preflight of run `fuelcast-phase1-20260928-002` passed:
canonical CSV SHA-256
`262428b4b2002435806f60aa9939755798dc9fe208b0c4b5d963a9200639cc65`,
audit SHA-256
`0f48b7a862703d7cf365d8299b0e32aad626866a963008ce39b12a4953fd264e`,
dataset version `eb6a6ec011c1c9a2cbce21459e22be4c77ef84dd`; vessel rows
`cps_poseidon` 105,422, `cps_triton` 25,347, `oss_ceto` 43,205, total
173,974. The selected `greenfleet.fuelcast_telemetry` collection is absent;
there are zero collection documents, active-version rows, conflicts, and
unsafe keys. The three required indexes to create are
`fuelcast_record_id_unique`, `fuelcast_dataset_version`, and
`fuelcast_vessel_time`. Preflight returned `safe_to_apply: true` and made no
database changes.

Final gate: focused tests 22 total (21 passed, one guarded integration skip);
full offline suite 48 total (47 passed, one guarded integration skip); both
database help commands and `git diff --check` passed; independent final code
review passed with no blocker or major findings. The opt-in live integration
test remains unrun by design. At that implementation gate, MongoDB `--apply`
had not yet run; the subsequent production load is recorded below. The Phase 3
commit `1f9705d2dab8006a2c764edde84adbc465949d5e` was pushed to
`origin/feat/fuelcast-e2e-clean`. Phase 3 is complete; Phase 4 is next.

### Phase 3 production load verification

The authorized `--apply` command used the approved canonical file at
`artifacts/fuelcast-phase1-20260928-002/02_etl/fuelcast_clean.csv` and wrote
to `greenfleet.fuelcast_telemetry`. The generated report is
`artifacts/fuelcast-phase1-20260928-002/03_mongodb/mongodb_load_report.json`.
It records 173,974 attempted, 173,974 inserted, 0 matched/skipped, 0 modified,
and 174 completed batches. Final collection and active-version counts are
173,974. Every expected ID and all required indexes were verified; canonical
conflicts, duplicate `record_id` values, duplicate active-version vessel/time
keys, and extra active-version IDs were all zero. A separate read-only
preflight recognized all 173,974 canonical rows, found zero conflicts and
zero indexes to create, and predicts zero inserts on another idempotent run.
No second write was performed. Legacy MongoDB collections/data must remain
untouched. Phase 4 must consume this canonical CSV, not the legacy merged
synthetic dataset or a mutable MongoDB query; Phase 4 has not started.

## Approved Phase 0 plan — repository foundation

Authorization: the current request explicitly asks to plan and implement Phase 0.
The inspection was read-only until this plan was recorded. Phase 0 is the only
implementation phase authorized by this plan.

### Baseline and call graph

- On branch `main`, `python -c 'import greenfleet'` fails because the local
  package is not installed. `PYTHONPATH=src python -c 'import greenfleet.ml_pipeline.pipeline'`
  succeeds in this checkout.
- `python -m unittest discover -s tests -v` cannot import its three test
  modules for the same package-path reason. With `PYTHONPATH=src`, five tests
  pass and the MongoDB test module cannot import because `pymongo` is absent.
- `pipeline.py`: `GreenFleetPipeline.run_pipeline` calls ingestion → validation
  → transformation, using the constructors and path argument those stages
  currently accept. `pipeline2.py` tries ingestion → validation → transformation
  → training but passes unsupported constructor arguments and artifact fields.
- `.gitignore` hides three Python artifact classes needed by the current stages.
  `PROJECT_ROOT` resolves to the repository root, and the transformation path
  constants are defined; no code change is needed for those two alleged defects.

### Exact change set and interfaces

1. Place the supplied `fuelcast_codex_docs/docs/` files at their expected
   `docs/` paths, preserving their contents; maintain the plan and handoff in
   `docs/`. Leave the original untracked supplied package untouched.
2. Change `.gitignore` from `artifacts/` to `/artifacts/`, and ignore generated
   `.greenfleet/` and `greenfleet.egg-info/` directories. Remove their already
   tracked contents, plus the two tracked root `artifacts/01_ingestion/` output
   files, from the Git index only; retain every local file. This large index
   cleanup is required because ignore rules do not affect tracked files.
3. Add the existing `data_validation_artifact.py`,
   `data_transformation_artifact.py` and `model_trainer_artifact.py` under
   `src/greenfleet/artifacts/` to source control. Their dataclass field names
   stay unchanged.
4. Keep `src/greenfleet/ml_pipeline/pipeline.py` as the sole orchestration
   implementation. Remove incompatible `pipeline2.py`, which has no tracked
   callers. Add a safe `--help` entry point and preserve the existing
   `GreenFleetPipeline` stage-method interface. No FuelCast execution is
   claimed in this phase.
5. Add focused foundation tests for package artifact imports, path constants,
   the single orchestrator and CLI help. Update only the stale Phase 0 portions
   of `README.md`, including setup guidance and known limitations.

No data/schema migration occurs. The legacy target, random split and
test-based trainer selection are documented incompatibilities to replace in
their assigned later phases; Phase 0 does not invoke the legacy trainer.

### Validation and gate

- `PYTHONPATH=src python -m unittest tests.test_foundation -v` (or equivalent
  discovery command if `tests` is not a package).
- `PYTHONPATH=src python -m greenfleet.ml_pipeline.pipeline --help`.
- `PYTHONPATH=src python -c 'import greenfleet.ml_pipeline.pipeline'`.
- Install the local package in an isolated environment, then run
  `python -c 'import greenfleet'` there to verify fresh-clone packaging.
- `PYTHONPATH=src python -m unittest discover -s tests -v`; document the
  pre-existing missing-`pymongo` error if the dependency remains unavailable.
- `git diff --check`, staged diff inspection, independent read-only test and
  reviewer gates. Stage only Phase 0 files, commit with
  `chore(pipeline): repair training foundation`, and push the feature branch
  only after both gates pass.

Risks: deleting `pipeline2.py` breaks external imports of that unsupported
module; no tracked callers exist. Index cleanup removes about 15,900 generated
files from future clones; the local environment remains available, and the
staged deletion list must be audited for unrelated files. The system Python
environment lacks project installation and `pymongo`, so dependency
availability can limit the full baseline suite. Rollback is a single Phase 0
commit revert; supplied docs and all unrelated working-tree changes remain
untouched.

## Final validation

```bash
python -m unittest discover -s tests -v
python -m greenfleet.ml_pipeline.pipeline --quick --skip-mongodb
git status
git diff --check
```

Run a separately authorized integration command for live FuelCast download and
MongoDB loading.

## Approved Phase 2 plan — FuelCast ETL

Authorization: the user supplied and approved the Phase 2 implementation plan.
Phase 1 commit `5336068` is pushed. Use local run
`fuelcast-phase1-20260928-002` at Hub SHA
`eb6a6ec011c1c9a2cbce21459e22be4c77ef84dd` for the live ETL check.

### Files and interfaces

- Extend `src/greenfleet/constants/fuelcast.py` with the exact seven-field
  source-to-canonical map, ordered 11-column output and units.
- Add `src/greenfleet/artifacts/fuelcast_etl_artifact.py` and
  `src/greenfleet/pipeline/etl/fuelcast.py` with
  `run_fuelcast_etl(run_dir: Path) -> FuelCastETLArtifact` and `--run-id`.
  Preserve the legacy ETL API and command.
- Verify the Phase 1 manifest and raw snapshot: dataset identity, revision,
  expected configurations, per-vessel counts, ordered columns, source schema
  fingerprints and snapshot SHA-256. Process each vessel separately.
- Remove exact duplicates, then invalid targets and times. Preserve feature
  nulls; audit numeric coercions and physical range violations, replacing
  invalid feature values with null. Reject conflicting vessel/time keys.
- Hash length-prefixed revision, vessel and integer time to form `record_id`;
  set `dataset_version` to revision. Stable-sort, write the canonical CSV and
  reconciled audit into a temporary stage, then publish without overwrite.
- Add `tests/test_fuelcast_etl.py` with three-vessel synthetic manifests and
  fixtures. Update README with the new FuelCast ETL command and contract.

No database or model migration occurs. The existing MongoDB contains synthetic
data and remains untouched in this phase.

### Validation and gate

Run focused and complete offline unittests, both ETL CLI help commands,
`git diff --check`, and independent read-only test/code reviews. Run the new
CLI against the selected local source snapshot and verify counts, hashes,
schema, uniqueness, sorting and ignored output. Inspect staged scope and diff,
commit as `feat(etl): add canonical FuelCast transformation`, push the feature
branch after a passing gate, and record the SHA in this plan and handoff.

Rollback is a scoped commit revert; local ignored `02_etl` symlink and its
`.02_etl-data-*` backing directory can be removed if needed. Source files
remain immutable.

## Approved Phase 1 plan — FuelCast ingestion

Authorization: the user supplied and approved this Phase 1 plan. Phase 0 commit
`1fdb30d` is pushed; its local SHA handoff edits will be included in this phase.

### Files and interfaces

- Add `src/greenfleet/constants/fuelcast.py` with dataset identity, ordered
  configurations, required source fields and raw snapshot column order.
- Add `src/greenfleet/artifacts/fuelcast_source_artifact.py` with snapshot and
  manifest paths, resolved Hub SHA and per-vessel row counts.
- Add `src/greenfleet/data_sources/{__init__,fuelcast,__main__}.py` exposing
  `ingest_fuelcast(run_dir: Path, revision: str | None = None) ->
  FuelCastSourceArtifact` and a `--run-id`/`--revision` CLI. The run writes
  `01_source/fuelcast_raw.csv` and `source_manifest.json` beneath `/artifacts/`.
- Resolve the dataset revision once with `HfApi.dataset_info`, pass the resolved
  SHA to configuration discovery and all three `train` loads, and reject missing
  expected configurations. Validate each declared Arrow schema before rows are
  converted: exact required names, integral `index`, numeric feature/target
  fields. Preserve row order and invalid values for ETL. Fingerprint ordered
  source name/type pairs and hash the final snapshot. Publish both outputs only
  after all loads succeed; refuse an existing run directory.
- Add `huggingface_hub` to `requirements.txt` and document the source command,
  provenance, license and phase boundary in `README.md`. No existing data or
  model contract is migrated in this phase.

### Tests and validation

Add `tests/test_fuelcast_source.py` with mocked Hub calls and three synthetic
configurations. Cover missing config/column, wrong declared type, SHA pinning,
output order and null preservation, counts, fingerprints, frozen timestamp,
overwrite refusal and no partial published output. Run focused and full offline
unittest suites, CLI `--help`, `git diff --check`, and staged diff checks. Then
run a unique live source CLI invocation and verify counts, hashes and ignore
behavior. Independent read-only test and reviewer agents gate the scoped commit
and push.

### Risks and rollback

Hub outages or schema changes fail clearly without publishing a snapshot. The
reported 173,986 rows is context, not an assertion. Do not commit source rows,
credentials, caches or runtime artifacts. Rollback is a revert of the Phase 1
commit and local removal of the ignored run directory if needed.

## Approved Phase 5 plan — bounded classical tuning

Authorization: the user supplied and requested implementation of the detailed
Phase 5 plan. Implementation, validation, commit and push belong to
`feat/fuelcast-classical-models`, based on `origin/main` at `60620a1`, which
already contains Phases 0–4. The authoritative local run is
`fuelcast-phase1-20260928-002`, pinned
to version `eb6a6ec011c1c9a2cbce21459e22be4c77ef84dd` and canonical SHA-256
`262428b4b2002435806f60aa9939755798dc9fe208b0c4b5d963a9200639cc65`.
Its Phase 4 train/validation arrays have 121,780 and 26,096 rows. Phase 5 must
neither open nor hash `test.npz`, fit preprocessing, or alter Phase 4 artifacts.

### Files and interfaces

Add `training/fuelcast_data.py` for explicit run resolution, source/hash/schema
and saved identity checks, loading only training and validation arrays. Add
`training/fuelcast_classical.py` for a `train` and `verify` CLI, bounded search,
validation metrics, per-vessel results and atomic mode publication. Add
`training/fuelcast_classical_model.py` for strict named-feature candidate reload.
Add corresponding typed settings, constants and artifact paths in the existing
`config`, `constants` and `artifacts` packages. Pin XGBoost and record dependency
versions. Add synthetic focused tests and update the README and phase handoffs.
No Phase 4 migration is required; the saved seven-column transformed arrays are
the input interface.

### Search and output

Use seed 42, a fixed Ridge grid and seeded parameter sampling for RF, GB and
XGBoost. Quick mode uses at most 1,000 evenly spaced training rows per vessel;
normal mode uses all training rows. Both modes score every trial on the complete
saved validation partition with MAE. Quick budgets are Ridge 3, RF 2, GB 2,
XGBoost 2; normal budgets are 5, 6, 6 and 8. RF and XGBoost use two fit threads;
XGBoost uses CPU histogram trees. Persist every trial, best parameters, model,
named schema and hashes, sampled IDs, validation predictions, overall and
per-vessel MAE/RMSE/R² and dependency versions. Publish a complete mode
directory after all four fresh-process reload checks pass. The leaderboard is
sorted by validation MAE and candidate name and declares only classical scope.

The exact search spaces are fixed in `constants/fuelcast_classical.py`:

| Candidate | Quick | Normal |
| --- | --- | --- |
| Ridge | `alpha=[0.1,1,10]` | `alpha=[0.01,0.1,1,10,100]` |
| Random Forest | `n_estimators=[40,60]`, `max_depth=[8,12]`, `min_samples_split=[2,5]`, `min_samples_leaf=[2,4]`, `max_features=[0.7,1]` | `n_estimators=[60,100,120]`, `max_depth=[8,12]`, `min_samples_split=[2,5,10]`, `min_samples_leaf=[2,4]`, `max_features=[0.7,1]` |
| Gradient Boosting | `n_estimators=[40,60]`, `learning_rate=[0.05,0.1]`, `max_depth=[2,3]`, `min_samples_split=[2,5]`, `subsample=[0.7,1]` | `n_estimators=[60,90,120]`, `learning_rate=[0.03,0.07,0.1]`, `max_depth=[2,3]`, `min_samples_split=[2,5,10]`, `subsample=[0.7,1]` |
| XGBoost | `n_estimators=[60,100]`, `learning_rate=[0.05,0.1]`, `max_depth=[3,5]`, `min_child_weight=[1,5]`, `subsample=[0.7,1]`, `colsample_bytree=[0.7,1]`, `reg_alpha=[0,0.1]`, `reg_lambda=[1,5]` | `n_estimators=[80,140,200]`, `learning_rate=[0.03,0.07,0.1]`, `max_depth=[3,5]`, `min_child_weight=[1,5,10]`, `subsample=[0.7,1]`, `colsample_bytree=[0.7,1]`, `reg_alpha=[0,0.1]`, `reg_lambda=[1,5]` |

### Gate, risks and rollback

Run focused synthetic tests, the full offline suite, quick and normal real
training where dependencies/resources permit, fresh-process verification, CLI
help and `git diff --check`. Independent read-only test and code reviewers gate
the scoped commit and push. The normal ensemble fits may take tens of minutes
and 1–3 GB; sequential trials, depth/tree caps and two worker threads bound
resource use. Missing XGBoost or macOS OpenMP must fail clearly before
publication. Retrying creates a fresh temporary stage; remove only unpublished
Phase 5 staging output after inspection. Preserve the published Phase 4 stage,
all canonical data and unrelated branches and changes.

Validation commands use the clean worktree's `PYTHONPATH=src` and the project's
`.greenfleet/bin/python`: `python -m unittest discover -s tests -p
'test_fuelcast_classical.py' -v`, `python -m unittest discover -s tests -v`,
`python -m greenfleet.ml_pipeline.training.fuelcast_classical --help`, and
`git diff --check`. Real runs pass the absolute pinned run, expected version and
canonical hash to `train --mode quick` followed by `train --mode normal`.
`verify` is run on every candidate in a fresh process before publication.

### Phase 5 validation note

During the first real normal run, a transient three-byte whitespace edit to
Phase 4 `feature_schema.json` changed its SHA-256, so fresh-process verification
rejected the candidate and removed the unpublished staging directory. The
altered bytes were backed up at
`/private/tmp/fuelcast-feature-schema-20260928-230906.modified.json`; the
original manifest-matching bytes were restored before reruns. No source rows,
preprocessor, partition arrays or split manifest were changed.

The restored pinned run produced complete, ignored `05_classical/quick` and
`05_classical/normal` directories. Fresh-process verification passed for each
candidate before either directory was published. Quick validation MAE ranked
Random Forest 0.122604, Gradient Boosting 0.143913, XGBoost 0.146567 and
Ridge 0.295065. Normal validation MAE ranked XGBoost 0.120164, Random Forest
0.120935, Gradient Boosting 0.131695 and Ridge 0.248201. These are classical
validation results only; no test score or production champion was produced.
Focused synthetic tests passed 9/9; the full offline suite passed 66 tests with
one opt-in integration skip. CLI help, explicit normal Ridge fresh-process
verification and `git diff --check` passed. Independent read-only test and code
reviews passed after count, metadata and guard fixes. Commit and push details
are reported with the phase completion record.

## Phase 0 gate results

- Branch: `feat/fuelcast-e2e-pipeline`.
- Foundation tests: 3/3 passed with `.greenfleet/bin/python`.
- Full offline suite: 11/11 passed with `.greenfleet/bin/python`.
- Package import, authoritative pipeline `--help`, `git diff --check`, and
  `git diff --cached --check`: passed.
- Independent test agent: PASS. Independent reviewer: PASS after generated
  directories were removed from the Git index.
- Staged scope includes the three imported Python artifact classes and excludes
  unrelated `AGENTS.md`, `.codex/`, and original `fuelcast_codex_docs/` changes.
- Phase 0 feature commit: `1fdb30d` (`chore(pipeline): repair training foundation`).
  Pushed to `origin/feat/fuelcast-e2e-pipeline` on 2026-09-28.
- This SHA record was written after the push and is a local handoff update;
  it will be included in the next scoped documentation commit rather than
  creating a second Phase 0 commit or rewriting the pushed one.

## Phase 1 gate results

- Focused source tests: 5/5 passed; full offline suite: 16/16 passed with
  `.greenfleet/bin/python`. Source CLI `--help` and `git diff --check` passed.
- Independent read-only test agent: PASS. Independent read-only reviewer: PASS;
  no blocker or major findings. Combined fingerprint coverage was added after
  review and the full suite reran successfully.
- Live source run: `fuelcast-phase1-20260928-002`, pinned Hub SHA
  `eb6a6ec011c1c9a2cbce21459e22be4c77ef84dd`; counts were 105,422
  `cps_poseidon`, 25,351 `cps_triton`, 43,213 `oss_ceto` (173,986 total).
  Manifest counts matched CSV rows, snapshot SHA-256 matched, and both outputs
  were ignored by Git. The generated run remains local under `/artifacts/`.
- Scoped staged-diff gate passed. Phase 1 commit: `5336068`
  (`feat(data): add FuelCast source ingestion`), pushed to
  `origin/feat/fuelcast-e2e-pipeline` on 2026-09-28. This SHA note was written
  after the push and remains local for the next scoped documentation commit.

## Phase 2 gate results

- Focused ETL tests: 10/10 passed; full offline suite: 26/26 passed with
  `.greenfleet/bin/python`. Both ETL CLI help commands and diff check passed.
- Independent test agent: PASS. Independent reviewer: PASS after source-byte
  consistency, atomic no-overwrite publication, and nonempty-vessel fixes.
- Live source run `fuelcast-phase1-20260928-002` produced 173,974 canonical
  rows: Poseidon 105,422; Triton 25,347; Ceto 43,205. Twelve missing time
  indexes were removed, with no target or duplicate removals. A fresh run from
  copied Phase 1 inputs produced a byte-identical canonical CSV. Output hash,
  schema, uniqueness, ordering, count reconciliation and Git ignore were checked.
- Original Phase 2 commit `c4235e2` was pushed to
  `origin/feat/fuelcast-e2e-pipeline`. The clean replay commit is `50dd953`;
  it was pushed on `feat/fuelcast-e2e-clean`.

## Clean branch recovery

The oversized original PR comparison was caused by Phase 0 removing 15,895
tracked `.greenfleet/` files, four `greenfleet.egg-info/` files and two
`artifacts/01_ingestion/` files. The feature branch also inherited local main
commit `c61bd08` (`classical training algorithm`), which is absent from
`origin/main`.

The approved recovery uses a separate worktree and a new branch from
`origin/main` (`026572d`). It replays the three reviewed phases in scoped
commits `9f527bb`, `dff071a` and `50dd953`, excluding generated-file deletions
and the unrelated classical commit. The necessary transformation path constants
from `c61bd08` were included in the clean Phase 0 replay because the baseline
model-training configuration imports them. The original branch and commits are
preserved. Full offline tests passed (26/26), and the clean comparison changes
33 files without generated-file deletions. The clean branch was pushed and
draft replacement PR #3 opened. Oversized PR #2 remains open and unchanged.
