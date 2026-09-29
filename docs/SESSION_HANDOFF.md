# FuelCast Session Handoff

## Phase 8 result (2026-09-29)

Phase 8 in `/private/tmp/fuelcast-phase8` uses branch
`feat/fuelcast-model-selection` from `origin/main` `0c025d7`. Five normal-mode
candidates were verified on the same 26,096 validation IDs. XGBoost won by
validation MAE 0.12016408036458692 kg/s; no refit occurred. A fresh-process
package check passed. The single final test evaluated 26,098 ordered unique
IDs: MAE 0.12854118081363877 kg/s, RMSE 0.1841633970560541, R²
0.8921833518766525. Per-vessel test MAE: Poseidon 0.111056, Triton 0.246247,
Ceto 0.102136 kg/s. Runtime outputs are under the pinned run's
`07_evaluation/` and `artifacts/final_model/`, ignored by Git.

Phase 8 focused tests passed 11/11; the offline suite ran 88 tests with seven
opt-in skips. Fresh-process verify, CLI help, hashes, ordered identities and
`git diff --check` passed. Independent read-only reviews found no remaining
blocker/major code issue after fixes. Phase 9 owns orchestration; QPSO-SVR
remains deferred. The original worktree remains untouched. Record the pushed
commit SHA here after the scoped commit and push.

## Current state

Phase 8 has completed selection and the one final test locally on
`feat/fuelcast-model-selection`; its scoped commit and push are pending. The
approved plan and measured results are in
`docs/plans/fuelcast_e2e_implementation.md`. Phase 6 QPSO-SVR remains
deferred. Phase 9 orchestration is next. Historical text below describes prior
phase entry conditions and validation-only work.

The authoritative run `fuelcast-phase1-20260928-002` produced a normal VQR
validation artifact with 600 sampled training rows, 80 COBYLA evaluations,
26,096 validation predictions and MAE `0.2830684142645837` kg/s. Quick mode
used 60 rows, 14 evaluations and all validation rows; its MAE was
`0.415270197450664` kg/s and is smoke evidence. Normal fresh-process verify,
11 guarded focused tests, the 70-pass/7-skip offline suite, independent code
and test reviews, and `git diff --check` passed. All runtime outputs are ignored.

The Phase 7 worktree is `/private/tmp/fuelcast-vqr`. The prior validation
worktree is `/private/tmp/fuelcast-e2e-clean`. The original
worktree at `/Users/subrat/Desktop/SIH` has unrelated local changes; preserve
them.

Phase 5 must use only `train.npz` and `validation.npz` from the pinned run. Do
not open or hash `test.npz`, refit Phase 4 preprocessing, use identity metadata
as model features, or rank on anything except validation MAE. The CLI takes
absolute run/version/canonical-checksum arguments. `05_classical/quick` and
`05_classical/normal` hold independent four-candidate experiments.
The Phase 4 schema briefly acquired a three-byte whitespace edit during a
real-run review, which its manifest hash correctly rejected. The altered copy
was saved under `/private/tmp` and original bytes restored; no arrays changed.
Both real `05_classical` modes subsequently completed: quick ranked Random
Forest first (validation MAE 0.122604); normal ranked XGBoost first (0.120164).
All four models in each mode passed fresh-process reload. These are ignored
validation-only outputs, not a frozen cross-family champion or test evaluation.
Phase 5 focused tests passed 9/9; the full offline suite passed 66 tests with
one opt-in integration skip. The classical leaderboard is validation-only and
does not select a production champion. No test score was produced.

## Authoritative FuelCast data and MongoDB state

- Dataset: `krohnedigital/FuelCast`, pinned dataset version
  `eb6a6ec011c1c9a2cbce21459e22be4c77ef84dd`.
- Canonical source: `artifacts/fuelcast-phase1-20260928-002/02_etl/fuelcast_clean.csv`
  under `/Users/subrat/Desktop/SIH`. Its SHA-256 is
  `262428b4b2002435806f60aa9939755798dc9fe208b0c4b5d963a9200639cc65`.
- MongoDB destination: **`greenfleet.fuelcast_telemetry`**.
- Canonical document count: **173,974** (`cps_poseidon` 105,422;
  `cps_triton` 25,347; `oss_ceto` 43,205).
- Load and verification report:
  `artifacts/fuelcast-phase1-20260928-002/03_mongodb/mongodb_load_report.json`
  under `/Users/subrat/Desktop/SIH`. It is a generated, ignored artifact.

The first load attempted 173,974 rows in 174 batches. It inserted 173,974,
matched or skipped 0 existing rows, and modified 0. The final collection count
and active-version count were both 173,974. Built-in post-load verification
found all 173,974 canonical IDs, zero canonical-content conflicts, zero
duplicate `record_id` values, zero duplicate active-version `(vessel_id,
time_index)` keys, and zero extra active-version IDs. It verified these three
indexes: unique `fuelcast_record_id_unique` on `record_id`,
`fuelcast_dataset_version` on `dataset_version`, and `fuelcast_vessel_time` on
`(vessel_id, time_index)`.

A subsequent **read-only** preflight found all 173,974 canonical IDs already
present, zero canonical conflicts, zero missing/null/duplicate `record_id`
keys, zero extra active-version IDs, and zero indexes required. A subsequent
idempotent load is therefore expected to insert 0 rows; this expectation was
not tested with a second write. The preflight was read-only.

Legacy MongoDB collections and their data must remain untouched. Never drop a
database or collection, reconcile by deletion, or run the legacy generic
loader against this canonical FuelCast destination.

## Exact Phase 4 starting point

The Phase 4 specification's objective is: **“Create the single saved data
contract consumed by every model family.”** Its required implementation is a
per-vessel chronological 70/15/15 train/validation/test split with saved row
IDs and time boundaries, strict ordering assertions, training-only median
imputation and standard scaling, circular wind-direction encoding, separate
VQR angle and target scaling interfaces, retained vessel/row identity, and
persisted partitions, preprocessors, feature schema, and split manifest.

Phase 4 must consume the **canonical FuelCast CSV and dataset version above**.
The MongoDB load proves persistence; model training must read the immutable
canonical file, not mutable MongoDB state. Do not silently fall back to the old
merged synthetic dataset, old `fuel_consumption_rate` target, or random split.
Do not begin implementation until a fresh Phase 4 spec-to-plan cycle is
approved and persisted. The Phase 4 table entry is still `pending`.

Read, in order: repository `AGENTS.md`; `docs/specs/fuelcast_e2e_pipeline.md`;
`docs/specs/phases/phase_04_transformation.md`;
`docs/decisions/fuelcast_decisions.md`;
`docs/plans/fuelcast_e2e_implementation.md`; and
`docs/handoffs/current_phase.md`. Then inspect the existing ETL, ML
transformation, artifact, constants, and test interfaces. For the phase gate,
use a read-only `repo_explorer` during planning, one `ml_engineer` writing
Phase 4 files after plan approval, and independent read-only `test_engineer`
and `reviewer` agents after implementation. Follow the repository's one-writer,
focused-test, full-test, diff-review, scoped-commit, and push rules.

## Git history and open items

The clean branch replayed Phase 0 as `9f527bb`, Phase 1 as `dff071a`, and
Phase 2 as `50dd953`. Phase 3 implementation is
`1f9705d2dab8006a2c764edde84adbc465949d5e`, followed by Phase 3 gate
documentation commits `e55c727`, `350b65b`, and `cb0cd24`. The original
branch `feat/fuelcast-e2e-pipeline` and its commits remain separate. This
handoff update is documentation only.

Open items and assumptions: Phase 4 has no approved phase-specific plan yet;
the local canonical CSV and ignored MongoDB report are not committed and must
be present in the execution environment; the opt-in isolated MongoDB
integration test was skipped during ordinary offline testing; the live
production load and read-only post-load preflight succeeded. Later model
dependency/version and VQR design decisions remain listed in
`docs/decisions/fuelcast_decisions.md`. Orchestrator wiring belongs to Phase 9.
