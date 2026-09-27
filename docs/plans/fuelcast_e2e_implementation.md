# FuelCast End-to-End Implementation Plan

## Status legend

- `pending`: not started
- `in_progress`: active phase
- `blocked`: cannot continue without a decision
- `passed`: implemented and phase gate accepted

| Phase | Name | Status | Depends on |
| --- | --- | --- | --- |
| 0 | Foundation | passed | none |
| 1 | FuelCast ingestion | passed | 0 |
| 2 | ETL | pending | 1 |
| 3 | MongoDB | pending | 2 |
| 4 | Split and preprocessing | pending | 2 |
| 5 | Classical tuning | pending | 4 |
| 6 | QPSO-SVR | pending | 4 |
| 7 | VQR | pending | 4 |
| 8 | Model selection | pending | 5, 6, 7 |
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
10. Push `feat/fuelcast-e2e-pipeline` to GitHub.
11. Record commit SHA, commands, test/review result and push state here and in
    the handoff.
12. Begin the next phase only after the push succeeds.

## Feature branch and commit plan

Branch: `feat/fuelcast-e2e-pipeline`

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
- Scoped commit and push: pending final staged-diff gate.
