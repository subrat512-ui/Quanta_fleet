# FuelCast End-to-End Implementation Plan

Current feature branch: `feat/fuelcast-e2e-clean`. Earlier references to
`feat/fuelcast-e2e-pipeline` describe the preserved original branch; new phases
use the clean branch. See `docs/SESSION_HANDOFF.md` for the latest operational
state and Phase 4 entry conditions.

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
| 4 | Split and preprocessing | in_progress | 2, 3 |
| 5 | Classical tuning | pending | 4 |
| 6 | QPSO-SVR | deferred | 4 |
| 7 | VQR | pending | 4 |
| 8 | Model selection | pending | 5, 7 |
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
10. Push `feat/fuelcast-e2e-clean` to GitHub.
11. Record commit SHA, commands, test/review result and push state here and in
    the handoff.
12. Begin the next phase only after the push succeeds.

## Feature branch and commit plan

Branch: `feat/fuelcast-e2e-clean`

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
- Scoped commit and push: pending final staged-diff gate.

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
