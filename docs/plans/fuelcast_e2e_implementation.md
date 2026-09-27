# FuelCast End-to-End Implementation Plan

## Status legend

- `pending`: not started
- `in_progress`: active phase
- `blocked`: cannot continue without a decision
- `passed`: implemented and phase gate accepted

| Phase | Name | Status | Depends on |
| --- | --- | --- | --- |
| 0 | Foundation | in_progress | none |
| 1 | FuelCast ingestion | pending | 0 |
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
- Phase 0 feature commit: pending. Push: pending. SHA: pending.
