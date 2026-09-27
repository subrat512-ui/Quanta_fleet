# FuelCast ETL, MongoDB and Model Training Specification

## Goal

Build one reproducible pipeline that imports the three configurations of
`krohnedigital/FuelCast`, produces a canonical dataset, persists it
idempotently to MongoDB, creates chronological model partitions, tunes
classical and quantum-inspired models, trains a simulator-based VQR and saves
one champion artifact.

## External source

- Dataset: https://huggingface.co/datasets/krohnedigital/FuelCast
- Dataset card/schema:
  https://huggingface.co/datasets/krohnedigital/FuelCast/blob/main/README.md
- Paper: https://arxiv.org/abs/2510.08217
- Configurations: `cps_poseidon`, `cps_triton`, `oss_ceto`
- License: CC BY-NC-ND 4.0
- Split exposed by each configuration: `train`
- Sampling interval: five minutes, represented by `index`

Do not commit or redistribute production dataset files.

## Canonical schema

| Source | Canonical | Role |
| --- | --- | --- |
| configuration | `vessel_id` | metadata |
| `index` | `time_index` | metadata |
| generated | `record_id` | persistence key |
| generated | `dataset_version` | provenance |
| `Ship_SpeedOverGround` | `speed_over_ground` | feature |
| `Weather_WindSpeed10M` | `wind_speed` | feature |
| `Weather_WindDirection10M` | `wind_direction` | feature |
| `Weather_WaveHeight` | `wave_height` | feature |
| `Weather_WavePeriod` | `wave_period` | feature |
| `Weather_OceanCurrentVelocity` | `current_speed` | feature |
| `Consumer_Total_MomentaryFuel` | `fuel_consumption_kg_s` | target |

Exclude individual fuel-consumption columns, power, RPM, torque, identifiers
and time metadata from version-1 model inputs.

## Pipeline

```text
FuelCast -> source manifest -> ETL -> canonical CSV -> MongoDB verification
         -> chronological split -> preprocessing -> candidate training
         -> validation leaderboard -> frozen champion -> final test
         -> inference artifact
```

MongoDB and training consume the same canonical dataset version. Training must
not depend on a new MongoDB query.

## ETL

- Validate every configuration separately.
- Require all source columns.
- Require unique `(vessel_id, time_index)`.
- Drop invalid targets and audit counts; never impute the target.
- Preserve missing feature values until ML preprocessing.
- Remove exact duplicates.
- Create stable `record_id` values.
- Sort by vessel and time.
- Save source manifest and ETL audit.

## MongoDB

- Database: `greenfleet`
- Collection: `fuelcast_telemetry`
- Upsert key: `record_id`
- Unique index: `record_id`
- Additional indexes: `dataset_version`, `(vessel_id, time_index)`
- Verify active-version counts after loading.
- Never persist credentials.

## Split

Within each vessel independently:

- first 70% training;
- next 15% validation;
- final 15% testing.

No shuffled or random row split. Persist row IDs and boundaries. Every model
family uses the exact same partitions.

## Preprocessing

- Fit only on training rows.
- Median-impute continuous features.
- Encode wind direction as sine and cosine.
- Standard-scale classical and QPSO-SVR inputs.
- Fit separate input-angle and target scalers for VQR.
- Persist every transformer.

## Classical candidates

- Ridge
- Random Forest
- Gradient Boosting
- XGBoost

Use bounded hyperparameter searches with the fixed validation partition.
Selection metric is validation MAE.

## Quantum-inspired candidate

QPSO searches `C`, `gamma` and `epsilon` for a classical RBF-SVR.
Use deterministic time-spaced training samples, initially capped at 4,000 rows
per vessel. Label it quantum-inspired and classical-hardware.

## Quantum candidate

Use Qiskit Machine Learning VQR with six inputs/qubits, a shallow ansatz,
training-fitted angle/target scaling and a simulator backend. Use a
representative deterministic sample and record all limitations.

## Evaluation

Report validation MAE/RMSE/R² for candidates and overall/per-vessel test
MAE/RMSE/R² for the frozen champion. Include timing, rows used, model family,
backend and versions.

## Selection protocol

1. Tune on training and validation only.
2. Rank by validation MAE.
3. Freeze champion and hyperparameters.
4. Optionally refit on train plus validation.
5. Evaluate once on untouched test rows.
6. Save model, preprocessing, schema, metrics, leaderboard and provenance.

## Final artifact

```text
artifacts/final_model/
├── model
├── preprocessor.pkl
├── model_manifest.json
├── feature_schema.json
├── metrics.json
└── leaderboard.json
```

The manifest records dataset ID/version, raw features, target, split strategy,
champion, model family, run ID, software versions and test metrics.

## Out of scope

Frontend, prediction API, route optimization, deployment, MLflow, real quantum
hardware and additional model features.

## Phase delivery protocol

For every phase:

1. read its specification;
2. enter Plan mode and inspect only its implementation area;
3. approve and persist the exact phase plan;
4. implement with one writing agent;
5. pass focused tests and independent broad review;
6. create one scoped feature commit;
7. push it to `feat/fuelcast-e2e-pipeline`;
8. update the plan and handoff with the commit SHA.

No later phase begins before the current phase passes and its feature commit is
pushed successfully.

## Done when

All configurations pass through ETL and MongoDB; partitions are reproducible;
classical/QPSO/VQR candidates use the shared data contract; selection has no
test leakage; the champion artifact reloads and predicts in a fresh process;
and focused plus synthetic end-to-end tests pass.
