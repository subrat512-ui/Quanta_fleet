# GreenFleet AI

> Quantum-inspired decision support for lower-emission maritime fleet operations.

GreenFleet AI is a modular platform for helping maritime operators balance fuel consumption, operating cost, and lifecycle greenhouse-gas emissions while meeting cargo, schedule, vessel, fuel-compatibility, and regulatory constraints.

The project is being built around one core principle: both the Genetic Algorithm (GA) and the quantum-inspired optimizer evaluate candidate fleet plans through the same objective and constraint framework. This makes their comparison meaningful, reproducible, and extensible.

## Vision

The platform will support end-to-end fleet planning:

- Predict vessel fuel consumption from operating and environmental conditions.
- Select vessels, cargo allocations, speeds, fuels, and shore-power use.
- Optimize competing fuel, cost, and emissions objectives.
- Compare GA and quantum-inspired search strategies over repeated runs.
- Model alternative-fuel, weather, price, demand, and emissions-policy scenarios.
- Present recommendations, constraints, trends, and reports through an API and web dashboard.

## Optimization model

For a candidate fleet plan `x`, GreenFleet AI minimizes a configurable weighted objective:

```text
J(x) = wf × Fuel(x) + wc × Cost(x) + we × Emissions(x)
```

where `wf + wc + we = 1`. Candidate plans are checked for cargo demand, vessel capacity, voyage time, speed bounds, fuel availability and compatibility, and emissions limits. Constraint handling belongs to the shared evaluator—not to individual optimizers.

```text
Candidate fleet plan
        │
        ▼
Shared evaluator ──► Fuel / cost / emissions objectives
        │
        ▼
Constraint checks and penalties
        │
        ▼
Fitness / feasibility result
        │
        ├── Genetic Algorithm
        └── Quantum-inspired optimizer
```

## Current implementation

The repository currently contains a data-foundation layer, partial ML training code, and a separate UI prototype:

- CSV and Parquet dataset extraction.
- Pinned Hugging Face FuelCast source ingestion with a raw snapshot and provenance manifest.
- Dataset validation, cleaning, transformation, and audit reporting.
- Command-line ETL workflow.
- Idempotent batched MongoDB loading of processed vessel telemetry.
- Read-only FuelCast MongoDB preflight and separately invoked canonical load.
- Structured logging and automated tests for the current pipeline.
- ML ingestion, validation, preprocessing, and regression-training components under `ml_pipeline/`, with integration gaps described below.
- A Streamlit prototype in `app.py`, branded "Green Quanta", with editable fleet and route tables and demonstration results.

The Streamlit results are hard-coded or synthetic; its Run Optimization button does not invoke a trained model or optimizer. Fleet-domain objects, prediction serving, the shared optimizer evaluator, GA, quantum-inspired optimization, scenarios, benchmarking, FastAPI, and the React dashboard are planned.

## Project layout

```text
Quanta_fleet/
├── src/greenfleet/         # Importable Python package (src layout)
│   ├── artifacts/         # Python stage-result classes; not generated datasets
│   ├── config/            # Configuration objects for each ML stage
│   ├── data_sources/      # Pinned FuelCast download and source validation
│   ├── constants/         # Dataset paths, feature names, target, defaults
│   ├── database/          # Batched MongoDB upserts and CLI
│   ├── entity/            # VesselRecord telemetry dataclass
│   ├── exception/         # Shared exception utility
│   ├── logging/           # Shared Python logging setup
│   ├── pipeline/etl/      # File extraction, validation, cleaning, export
│   └── ml_pipeline/       # In-progress model-training workflow
│       ├── ingestion/     # Copy source data and record metadata
│       ├── validation/    # Check training schema and data quality
│       ├── transformation/ # Split data, preprocess, persist arrays
│       ├── training/      # Compare regressors and save best model
│       └── pipeline.py   # Sole legacy ML orchestrator; FuelCast flow pending
├── tests/                 # ETL and MongoDB loader unit tests
├── app.py                 # Standalone Streamlit demonstration
├── test.py                # Manual CSV inspection script, requires local data
├── setup.py               # Installs greenfleet from src/
├── requirements.txt       # Core dependencies
├── README.md              # User-facing setup, structure, and status
└── AGENTS.md              # Contributor guidance and long-term design
```

Local `data/` holds datasets; root `artifacts/` holds generated pipeline outputs; `logs/` holds runtime logs. These differ from the Python classes in `src/greenfleet/artifacts/`. The checkout also contains environment/package metadata (`.greenfleet/`, `greenfleet.egg-info/`), which is not application source. Create your own environment rather than relying on the checked-in environment.

### How the pieces connect

```text
Source CSV/Parquet -> pipeline/etl -> cleaned dataset + JSON audit
                                           |
                                           +-> database -> MongoDB (optional)

Prepared training CSV -> ml_pipeline/ingestion -> validation
                        -> transformation -> training (integration incomplete)

app.py -> Streamlit demo with synthetic results (separate from both pipelines)
```

ETL normalizes column names, removes duplicate rows, fills missing values, and creates a `record_id`. ML transformation handles the train/test split, numeric imputation/scaling, categorical encoding, and saved preprocessing artifacts. The trainer compares Linear Regression, Random Forest, and Gradient Boosting using MAE, RMSE, and R-squared, selecting the highest test R-squared. A separate validation strategy is still needed before treating that score as an unbiased final evaluation.

### Current ML integration status

`ml_pipeline/pipeline.py` is the only ML orchestration entry point. It runs the existing ingestion, validation, and transformation stages. The incompatible `pipeline2.py` path was removed. Source artifact classes are tracked separately from generated root `artifacts/`, and configured paths resolve from the repository root.

This legacy ML path is not the FuelCast training pipeline yet. It still expects the older `fuel_consumption_rate` schema and uses a random train/test split. Do not use its output as FuelCast benchmark evidence. The documented FuelCast source, canonical target, chronological split, and model training will be added in their assigned phases under `docs/specs/phases/`.

## Getting started

### Prerequisites

- Python 3.10 or later
- MongoDB (only needed for the database-loading step)

### Install

```bash
git clone https://github.com/subrat512-ui/Quanta_fleet.git
cd Quanta_fleet

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

### Download FuelCast source data

FuelCast comes from KROHNE Digital's [`krohnedigital/FuelCast`](https://huggingface.co/datasets/krohnedigital/FuelCast) dataset on Hugging Face. The source stage resolves a Hub commit SHA and loads the `train` split of `cps_poseidon`, `cps_triton`, and `oss_ceto` at that exact revision. It validates each declared source schema and writes `artifacts/<run-id>/01_source/fuelcast_raw.csv` plus `source_manifest.json`. The manifest records the SHA, retrieval time, source schema fingerprints, row counts, and snapshot hash. An existing run directory is never overwritten.

```bash
python -m greenfleet.data_sources --run-id fuelcast-20260928
# To resolve a particular Hub tag, branch, or commit:
python -m greenfleet.data_sources --run-id fuelcast-pinned --revision <revision>
```

FuelCast is licensed [CC BY-NC-ND 4.0](https://huggingface.co/datasets/krohnedigital/FuelCast/blob/main/README.md). Use it only in the authorized project context. Do not commit or redistribute downloaded rows. The source stage preserves missing and invalid values for the canonical ETL audit.

### Canonicalize a FuelCast source run

```bash
python -m greenfleet.pipeline.etl.fuelcast --run-id fuelcast-20260928
```

This validates the pinned source manifest and snapshot, then writes
`artifacts/<run-id>/02_etl/fuelcast_clean.csv` and `etl_audit.json`. It retains
only the approved six features, renames the total fuel target to
`fuel_consumption_kg_s`, removes invalid targets and times, and preserves missing
features for training-only preprocessing. The audit records removals and feature
quality by vessel. An existing ETL stage is never overwritten. FuelCast model
training remains a later phase.

### Inspect and load canonical FuelCast into MongoDB

Export `MONGODB_URI` in the process environment. The FuelCast command reads
credentials only from that variable and does not load `.env` files. Its default
mode validates the ETL CSV and audit, then performs a read-only database
preflight. It prints database and collection existence, existing counts and
indexes, expected IDs already present, and any conflicts. Use the run ID from
the completed ETL stage:

```bash
python -m greenfleet.database.fuelcast --run-id fuelcast-20260928 --preflight-only
```

After reviewing a safe preflight, explicitly request the load:

```bash
python -m greenfleet.database.fuelcast --run-id fuelcast-20260928 --apply
```

The default destination is `greenfleet.fuelcast_telemetry`; `--database` and
`--collection` can select another destination. Apply repeats preflight, creates
missing required indexes, and upserts by deterministic `record_id` in unordered
batches of 1,000. Existing matching documents and their extra fields are
preserved. Any conflict blocks writes. Each apply attempt writes a sanitized
`artifacts/<run-id>/03_mongodb/mongodb_load_report.json`, including verification
of active-version counts, row IDs and canonical values. A partial write can be
replayed safely; the loader never deletes records or indexes. Do not commit
FuelCast data, MongoDB credentials or runtime reports.

### Run the existing ETL pipeline

The ETL command reads a source CSV, validates and normalizes it, writes the processed dataset, and produces an audit report.

Supply your own source file. The default input schema requires `Sailing speed`, `Displacement`, `Wind speed`, `Fuel consumption rate`, and `vessel_type`; the fuel column must be numeric. This command expects raw input, not a previously normalized output containing `record_id`. Parquet support requires an engine such as `pyarrow`.

```bash
python -m greenfleet.pipeline.etl \
  data/raw/vessel_telemetry.csv \
  data/processed/vessel_telemetry.csv \
  --audit data/processed/vessel_telemetry.audit.json
```

The output summary includes input/output row counts, run duration, validation results, and transformation statistics.

### Load processed telemetry into MongoDB

Configure the connection in a local `.env` file (which is intentionally ignored by Git):

```dotenv
MONGODB_URI=mongodb://localhost:27017
MONGODB_DATABASE=greenfleet
MONGODB_COLLECTION=vessel_telemetry
```

Then run the loader. Rows are upserted using `record_id` by default, so repeated loads do not duplicate observations.

```bash
python -m greenfleet.database \
  data/processed/vessel_telemetry.csv \
  --key-field record_id \
  --batch-size 1000
```

### Run tests

The existing tests use standard-library `unittest` and mock database access; no live MongoDB server is required.

```bash
python -m unittest discover -s tests -v
```

Alternatively, install `pytest` separately and run `python -m pytest tests/`.

### Run the UI prototype

Streamlit is not currently listed in `requirements.txt`. Install it separately:

```bash
python -m pip install streamlit
python -m streamlit run app.py
```

Open the URL printed by Streamlit (normally `http://localhost:8501`). Displayed savings, feasibility labels, and fleet assignments are demonstration data, not verified optimization results.

## Planned architecture

```text
React + TypeScript dashboard
            │ REST API
            ▼
         FastAPI
            │
  ┌─────────┼────────────┐
  ▼         ▼            ▼
Prediction  Optimization  Scenario / benchmark services
  │           │
ML model  GA + Quantum-inspired search
              │
       Shared fleet evaluator
              │
     Fuel, cost, emissions, constraints
              │
       MongoDB / MLflow results
```

## Roadmap

1. Repair ML artifact tracking, configuration paths, and stage interfaces; validate dataset/target semantics and complete fuel-prediction baselines.
2. Define fleet, vessel, voyage, fuel, solution, objectives, and constraints.
3. Implement the shared evaluator and a reproducible Genetic Algorithm baseline.
4. Add the isolated quantum-inspired encoding, sampling, and update engine.
5. Add scenario analysis and multi-run benchmarking with convergence metrics.
6. Expose services through FastAPI, then build the React decision-support dashboard.
7. Package the full stack with Docker and deployment automation.

## Quantum-inspired fuel prediction prototype

The repository includes a separate QPSO-tuned RBF Support Vector Regression
trainer. Quantum-behaved particle swarm optimization searches the SVR `C`,
`gamma`, and `epsilon` values on classical hardware. Preprocessing is fitted
inside every validation fold, and the final artifact contains both preprocessing
and prediction steps.

Train with the default project feature schema:

```bash
python -m greenfleet.ml_pipeline.quantum data/final/maritime_fuel_clean.csv
```

For a smaller prototype schema, provide comma-separated feature lists:

```bash
python -m greenfleet.ml_pipeline.quantum synthetic_fleet.csv \
  --target fuel_tonnes_per_day \
  --numerical-features speed_knots,load_fraction,wind_speed_ms,wave_height_m \
  --categorical-features vessel_type \
  --group-column voyage_id
```

Outputs are written to `artifacts/04_quantum_model/` by default. The JSON report
records held-out MAE, RMSE, R-squared, validation MAE, search parameters, search
history, and data-quality warnings. With synthetic data, these scores measure how
well the model reproduces the simulator and are not evidence of field accuracy.

## Technology stack

| Area | Tools |
| --- | --- |
| Language | Python |
| Data processing | Pandas, NumPy |
| Data ingestion | Hugging Face Datasets |
| Storage | MongoDB / PyMongo |
| Configuration | python-dotenv, PyYAML |
| ML components | scikit-learn; XGBoost and MLflow are planned |
| UI prototype | Streamlit (installed separately) |
| Planned API and UI | FastAPI, React, TypeScript, Plotly, Tailwind CSS |
| Testing | unittest; optional pytest runner |

## Contributing

Keep domain calculations out of API routes and optimizer implementations. New search algorithms should use the same evaluator; new datasets and models should remain replaceable through configuration. Please add or update focused tests with each functional change.

## License

No license has been specified yet. Add one before distributing or reusing this project externally.
