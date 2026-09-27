# Phase 9 — End-to-End Orchestration

## Objective

Connect all accepted stages through one resumable CLI workflow.

## Requirements

- One authoritative `greenfleet.ml_pipeline.pipeline` entry point.
- Sequence ingestion, ETL, optional MongoDB, transformation, candidate training,
  evaluation and final artifact publication.
- Support `--skip-download`, `--skip-mongodb`, `--classical-only`,
  `--skip-vqr`, `--quick` and `--run-id`.
- Validate prerequisite artifacts when stages are skipped.
- Preserve run/dataset identity across stages.
- Fail clearly and leave completed artifacts inspectable.
- Update README with source, license, commands and limitations.

## Tests

Run synthetic end-to-end quick mode without network or MongoDB, CLI help tests,
resume/skip tests and final artifact inference.

## Gate

Before editing, enter Plan mode and persist CLI, resume, failure and end-to-end
validation decisions. After the full suite and broad final review PASS, commit
as `feat(pipeline): add FuelCast end-to-end orchestration`, push and record the
SHA. Do not merge or open a PR unless separately requested.

Focused tests and the full suite pass; synthetic quick mode produces a champion
artifact; separately authorized live integration steps are documented.
