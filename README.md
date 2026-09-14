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

The repository currently provides the data-foundation layer:

- CSV and Parquet dataset extraction.
- Dataset validation, cleaning, transformation, and audit reporting.
- Command-line ETL workflow.
- Idempotent batched MongoDB loading of processed vessel telemetry.
- Structured logging and automated tests for the current pipeline.

Prediction models, fleet-domain objects, the shared optimizer evaluator, GA, quantum-inspired optimization, scenarios, benchmarking, FastAPI, and the React dashboard are planned next. See the roadmap below.

## Project layout

```text
src/greenfleet/
├── database/              # MongoDB telemetry ingestion
├── entity/                # Data schemas
├── exception/             # Project exceptions
├── logging/               # Shared logging setup
└── pipeline/etl/          # Extract, validate, transform, load workflow
tests/                     # ETL and MongoDB loader tests
data/                      # Local datasets (raw/processed paths are ignored)
```

## Getting started

### Prerequisites

- Python 3.10 or later
- MongoDB (only needed for the database-loading step)

### Install

```bash
git clone <your-repository-url>
cd SIH

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

### Run the ETL pipeline

The ETL command reads a source CSV, validates and normalizes it, writes the processed dataset, and produces an audit report.

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

```bash
python -m pytest
```

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

1. Complete data analysis, feature engineering, and fuel-prediction baselines.
2. Define fleet, vessel, voyage, fuel, solution, objectives, and constraints.
3. Implement the shared evaluator and a reproducible Genetic Algorithm baseline.
4. Add the isolated quantum-inspired encoding, sampling, and update engine.
5. Add scenario analysis and multi-run benchmarking with convergence metrics.
6. Expose services through FastAPI, then build the React decision-support dashboard.
7. Package the full stack with Docker and deployment automation.

## Technology stack

| Area | Tools |
| --- | --- |
| Language | Python |
| Data processing | Pandas, NumPy |
| Data ingestion | Hugging Face Datasets |
| Storage | MongoDB / PyMongo |
| Configuration | python-dotenv, PyYAML |
| Planned ML | scikit-learn, XGBoost, MLflow |
| Planned API and UI | FastAPI, React, TypeScript, Plotly, Tailwind CSS |
| Testing | pytest |

## Contributing

Keep domain calculations out of API routes and optimizer implementations. New search algorithms should use the same evaluator; new datasets and models should remain replaceable through configuration. Please add or update focused tests with each functional change.

## License

No license has been specified yet. Add one before distributing or reusing this project externally.
