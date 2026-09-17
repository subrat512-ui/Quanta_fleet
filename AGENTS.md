# GreenFleet AI

> Quantum-Inspired Decision Support System for Green Fleet Management

## Repository Guidance: Current Implementation

Read this section before the product design below. Sections 1-25 describe the
target platform and its requirements; they do not claim that all modules exist.
Use the current `src/greenfleet/` layout for changes. Do not create or migrate to
the illustrative `app/` tree merely to match the long-term architecture.

### Current Structure and Ownership

| Path | Responsibility |
| --- | --- |
| `src/greenfleet/pipeline/etl/` | File extraction, schema validation, normalization, cleaning, dataset export, audit reports, CLI |
| `src/greenfleet/database/` | MongoDB conversion, unique-key validation, batched upserts, CLI |
| `src/greenfleet/ml_pipeline/` | In-progress ingestion, validation, preprocessing, regression training, and two orchestration variants |
| `src/greenfleet/config/` | ML stage configuration objects |
| `src/greenfleet/constants/` | Paths, required columns, feature lists, target, default parameters |
| `src/greenfleet/artifacts/` | Python result/metadata classes passed between stages |
| `src/greenfleet/entity/` | Existing `VesselRecord` telemetry schema; not fleet optimization domain models |
| `src/greenfleet/logging/`, `exception/` | Shared logging and exception helpers |
| `tests/` | ETL and MongoDB loader unit tests |
| `app.py` | Standalone Streamlit UI demo with hard-coded/synthetic output |
| `test.py` | Manual inspection of a local CSV, not the automated test suite |
| `setup.py`, `requirements.txt` | Package installation and core dependencies |

Root `artifacts/` contains generated outputs and is distinct from source classes
in `src/greenfleet/artifacts/`. Local data and logs are runtime inputs/outputs.
`.greenfleet/` and `greenfleet.egg-info/` are environment/package metadata, not
application modules. Avoid editing or adding generated environment files.

### Implementation Status and Known Gaps

- ETL and MongoDB loading have implementations and focused unit tests.
- ML stages exist, but the training workflow is not yet integrated reliably.
  `pipeline.py` ends at transformation; `pipeline2.py` attempts training with
  stage constructor arguments and artifact fields that do not match the current
  components. Reconcile these interfaces before documenting a working trainer CLI.
- Validation, transformation, and trainer artifact modules are local-only:
  the `artifacts/` ignore pattern also matches the Python source directory.
  Only the artifact package initializer, base class, and ingestion class are
  currently tracked. Fresh clones therefore lack required imports.
- `model_trainer_config.py` imports undefined `TRANSFORMED_TRAIN_FILE` and
  `TRANSFORMED_TEST_FILE` constants. `PROJECT_ROOT` currently resolves to `src/`
  rather than the repository root. Verify paths before running ML stages.
- The configured ML target is `fuel_consumption_rate`; establish units and
  source semantics through dataset analysis. The older `VesselRecord` schema
  uses `total_momentary_fuel` and should not be assumed interchangeable.
- Streamlit is an optional install not listed in `requirements.txt`. The demo
  does not call the ML pipeline or any real optimizer; never cite its numbers
  as benchmark, feasibility, or emissions evidence.
- Shared fleet evaluation, GA, quantum-inspired search, scenarios, benchmarking,
  prediction serving, FastAPI, React, MLflow integration, and Docker deployment
  remain planned work.

### Development Commands

From the repository root, use a dedicated Python 3.10+ environment:

```bash
python -m pip install -r requirements.txt
python -m pip install -e .
python -m unittest discover -s tests -v
python -m greenfleet.pipeline.etl --help
python -m greenfleet.database --help
```

The tests mock database access. `pytest` is an optional runner installed
separately; use `python -m pytest tests/`. To run the demo, install `streamlit`
and use `python -m streamlit run app.py`. See README.md for dataset prerequisites
and MongoDB environment variables. Do not run `test.py` as a general test command.

### Change Guidelines

- Keep ETL cleaning, ML preprocessing/training, persistence, and UI concerns in
  their existing modules. Preserve the shared-evaluator requirement below when
  adding optimization; UI and search algorithms must not duplicate domain math.
- Keep README.md aligned with tracked source and separate implemented behavior,
  prototypes, integration gaps, and planned features.
- Add focused tests for behavior changes. Document validation limitations when
  dependencies or external services are unavailable.
- Do not commit credentials, local datasets, model outputs, archives, or new
  environment files. Stage explicit task files; preserve unrelated user changes.
- Repair the ML foundation before extending the downstream platform. Do not
  implement the entire roadmap as part of a documentation or small feature task.

## 1. Project Overview

GreenFleet AI is a modular software platform for sustainable maritime
fleet management.

The platform combines:

-   Machine-learning based fuel-consumption prediction
-   Multi-objective fleet optimization
-   Genetic Algorithm (GA)
-   Quantum-inspired optimization
-   Alternative-fuel scenario analysis
-   Constraint handling
-   Algorithm benchmarking
-   Fleet, fuel, cost and emission visualization
-   Report generation

The goal is to help fleet operators determine an operational plan that
balances:

1.  Fuel consumption
2.  Operational cost
3.  Lifecycle greenhouse-gas emissions

while satisfying cargo demand, voyage schedule, vessel capabilities,
fuel compatibility and emission constraints.

------------------------------------------------------------------------

## 2. Problem Statement

Maritime and logistics operations face increasing pressure to reduce
greenhouse-gas emissions without sacrificing operational efficiency.

Fleet decisions are inherently complex because they involve:

-   Different vessel types and capacities
-   Different cruising speeds
-   Multiple fuel options
-   Alternative fuels such as LNG, methanol, hydrogen and ammonia
-   Shore-power availability
-   Dynamic weather and sea conditions
-   Cargo requirements
-   Schedule constraints
-   Fuel prices
-   Emission regulations

GreenFleet AI models these decisions as a constrained multi-objective
optimization problem.

------------------------------------------------------------------------

## 3. Core System

``` text
                    GREENFLEET AI
                         |
             +-----------+-----------+
             |                       |
       PREDICTION                OPTIMIZATION
             |                       |
       Fuel Prediction        +-------+-------+
                              |               |
                             GA       Quantum-Inspired
                              |               |
                              +-------+-------+
                                      |
                                  EVALUATOR
                                      |
                    +-----------------+----------------+
                    |                 |                |
                   Fuel              Cost          Emissions
                    |                 |                |
                    +-----------------+----------------+
                                      |
                                  Constraints
                                      |
                                Optimal Solution
                                      |
                         +------------+-------------+
                         |            |             |
                     Scenarios    Benchmark      Reports
```

------------------------------------------------------------------------

# 4. Main Features

## 4.1 Fuel Consumption Prediction

The prediction module estimates vessel fuel consumption from operational
and environmental conditions.

Example inputs include:

-   Vessel type
-   Fuel type
-   Speed over ground
-   Speed through water
-   Shaft power
-   Engine rotation speed
-   Wind speed/direction
-   Wave height/period/direction
-   Ocean-current velocity/direction
-   Temperature
-   Pressure
-   Other available weather variables

Example output:

``` text
Predicted Fuel Consumption
128.4 kg/h

Estimated Voyage Fuel
9.24 tonnes
```

The prediction engine is designed as a replaceable ML component so
different regression models can be trained and benchmarked.

------------------------------------------------------------------------

# 5. Fleet Optimization

The optimization engine determines a feasible fleet operating plan.

## Decision Variables

Depending on the scenario, the optimizer can decide:

-   Vessel selection
-   Vessel allocation
-   Cargo allocation
-   Vessel capacity utilization
-   Cruising speed
-   Fuel type
-   Alternative-fuel selection
-   Shore-power usage

A solution can conceptually be represented as:

``` text
FleetSolution = {
    vessel_assignments,
    cargo_allocations,
    speeds,
    fuel_choices,
    shore_power_choices
}
```

------------------------------------------------------------------------

# 6. Multi-Objective Optimization

The system minimizes multiple objectives simultaneously.

### Fuel

``` text
minimize F(x)
```

### Operational Cost

``` text
minimize C(x)
```

### Greenhouse-Gas Emissions

``` text
minimize E(x)
```

A weighted formulation can be used for a configurable operating mode:

``` text
J(x) = wf * F(x)
     + wc * C(x)
     + we * E(x)

where:

wf + wc + we = 1
```

The UI exposes these priorities so the user can determine whether fuel,
cost or environmental impact should receive greater importance.

------------------------------------------------------------------------

# 7. Constraints

Candidate solutions must satisfy the configured operational constraints.

Examples:

``` text
Cargo Demand >= Required Cargo

Voyage Time <= Maximum Allowed Time

Minimum Speed <= Vessel Speed <= Maximum Speed

Cargo Allocation <= Vessel Capacity

Selected Fuel must be compatible with Vessel

Required Fuel must be available

Emissions <= Regulatory Limit
```

The evaluator is responsible for checking feasibility.

------------------------------------------------------------------------

# 8. Common Evaluator

The Genetic Algorithm and Quantum-Inspired optimizer must use the same
evaluation framework.

``` text
             Candidate Solution
                     |
                     v
                Evaluator
                     |
        +------------+------------+
        |            |            |
       Fuel         Cost      Emissions
        |            |            |
        +------------+------------+
                     |
                Constraints
                     |
                     v
              Objective Value
```

This is critical for a fair algorithm comparison.

The optimizers are responsible for searching the solution space; the
evaluator is responsible for determining how good a solution is.

------------------------------------------------------------------------

# 9. Genetic Algorithm

The Genetic Algorithm is the conventional metaheuristic baseline.

High-level workflow:

``` text
Initialize Population
        |
        v
Evaluate Population
        |
        v
Selection
        |
        v
Crossover
        |
        v
Mutation
        |
        v
Repair Infeasible Solutions
        |
        v
Evaluate
        |
        v
Elitism
        |
        v
Repeat
        |
        v
Best Solution
```

The GA should operate through the common optimization interfaces rather
than containing domain-specific fuel or emission calculations.

------------------------------------------------------------------------

# 10. Quantum-Inspired Optimization

The second optimizer uses a quantum-inspired representation and update
mechanism while running on classical computing infrastructure.

Conceptual workflow:

``` text
Initialize Quantum-Inspired State
              |
              v
       Encode Solution
              |
              v
           Sample
              |
              v
      Generate Candidates
              |
              v
          Evaluate
              |
              v
       Update State
              |
              v
          Repeat
              |
              v
       Best Solution
```

The exact encoding, state representation and update mechanism should
remain isolated inside the quantum optimizer module.

This allows the optimization framework to evolve without changing the
rest of the application.

------------------------------------------------------------------------

# 11. Scenario Analysis

Scenario analysis evaluates how the optimal strategy changes under
different conditions.

Supported scenario dimensions may include:

-   Fuel price
-   Cargo demand
-   Weather severity
-   Wind conditions
-   Wave conditions
-   Carbon/emission cost
-   Emission limits
-   Fuel availability
-   Alternative-fuel adoption

Example:

``` text
Base Scenario
       |
       +---- High Fuel Price
       |
       +---- Severe Weather
       |
       +---- High Cargo Demand
       |
       +---- Strict Emission Regulation
       |
       +---- Green Fuel Transition
```

Each scenario modifies a problem configuration and is passed through the
same optimization pipeline.

------------------------------------------------------------------------

# 12. Benchmarking

The platform compares the Genetic Algorithm and Quantum-Inspired
optimizer.

Metrics include:

-   Best objective value
-   Mean objective value
-   Worst objective value
-   Standard deviation
-   Runtime
-   Convergence speed
-   Constraint feasibility
-   Solution quality
-   Scalability

Because metaheuristic algorithms are stochastic, benchmarking should use
multiple independent runs.

Example:

``` text
                    GA       Quantum-Inspired
------------------------------------------------
Best Objective      ...            ...
Mean Objective      ...            ...
Std Deviation       ...            ...
Runtime             ...            ...
Iterations          ...            ...
```

Convergence curves should also be visualized.

------------------------------------------------------------------------

# 13. User Interface

The application is designed as a decision-support dashboard rather than
a raw ML/optimization console.

## Main Navigation

``` text
Dashboard
Fleet Management
Fuel Prediction
Optimization
Scenario Analysis
Benchmarking
Reports
Settings
```

## Dashboard

Displays:

-   Total vessels
-   Fuel consumption
-   GHG emissions
-   Operational cost
-   Schedule status
-   Fuel-consumption trends
-   Emission profile by fuel
-   Current fleet allocation
-   Optimization summary
-   Recent scenarios
-   Algorithm comparison
-   Quick actions

## Fuel Prediction

Users provide vessel, operational and weather inputs and receive
predicted fuel consumption.

## Optimization

Users configure:

-   Voyage
-   Cargo demand
-   Fleet
-   Available fuels
-   Shore power
-   Objective priorities
-   Constraints
-   Optimization algorithm

The output contains the recommended fleet plan and performance metrics.

## Scenario Analysis

Users create or select scenarios and compare the resulting fleet
strategies.

## Benchmarking

Users compare GA and Quantum-Inspired performance.

## Reports

Users can generate a report containing:

-   Input configuration
-   Recommended fleet plan
-   Fuel consumption
-   Cost
-   Emissions
-   Constraint status
-   Algorithm comparison
-   Scenario analysis
-   Benchmark results

------------------------------------------------------------------------

# 14. High-Level Architecture

``` text
                    +----------------------+
                    |    React Frontend    |
                    |     TypeScript       |
                    +----------+-----------+
                               |
                            REST API
                               |
                    +----------v-----------+
                    |       FastAPI        |
                    |      API Layer       |
                    +----------+-----------+
                               |
                    +----------v-----------+
                    |    Service Layer     |
                    +----------+-----------+
                               |
       +-----------------------+-----------------------+
       |                       |                       |
       v                       v                       v
Prediction Service     Optimization Service     Scenario Service
       |                       |                       |
       v                 +-----+-----+                 |
ML Prediction Model      |           |                 |
                         v           v                 |
                        GA      Quantum-Inspired       |
                         |           |                 |
                         +-----+-----+-----------------+
                               |
                               v
                          Fleet Evaluator
                               |
                     +---------+---------+
                     |         |         |
                    Fuel      Cost    Emissions
                               |
                               v
                          Result Manager
                               |
                    +----------+----------+
                    |                     |
                    v                     v
                 MongoDB               MLflow
```

------------------------------------------------------------------------

# 15. Low-Level Architecture

## Planned Repository (Conceptual)

This tree illustrates future responsibilities, not the current checkout.
The current repository uses `src/greenfleet/`, as documented above; introducing
new modules should follow that package layout unless an explicit migration is
requested. The root `app.py` is a Streamlit prototype, not this proposed `app/`
backend package.

``` text
greenfleet/
│
├── app/
│   ├── api/
│   │   ├── routes/
│   │   │   ├── prediction.py
│   │   │   ├── optimization.py
│   │   │   ├── scenario.py
│   │   │   ├── benchmark.py
│   │   │   └── reports.py
│   │   └── dependencies.py
│   │
│   ├── services/
│   │   ├── prediction_service.py
│   │   ├── optimization_service.py
│   │   ├── scenario_service.py
│   │   ├── benchmark_service.py
│   │   └── report_service.py
│   │
│   ├── prediction/
│   │   ├── data/
│   │   │   ├── ingestion.py
│   │   │   ├── validation.py
│   │   │   └── transformation.py
│   │   ├── features/
│   │   │   └── feature_engineering.py
│   │   ├── training/
│   │   │   ├── trainer.py
│   │   │   └── evaluator.py
│   │   └── inference/
│   │       └── predictor.py
│   │
│   ├── optimization/
│   │   ├── domain/
│   │   │   ├── vessel.py
│   │   │   ├── fuel.py
│   │   │   ├── fleet.py
│   │   │   ├── voyage.py
│   │   │   ├── solution.py
│   │   │   └── problem.py
│   │   │
│   │   ├── objectives/
│   │   │   ├── fuel.py
│   │   │   ├── cost.py
│   │   │   ├── emissions.py
│   │   │   └── multi_objective.py
│   │   │
│   │   ├── constraints/
│   │   │   ├── cargo.py
│   │   │   ├── capacity.py
│   │   │   ├── schedule.py
│   │   │   ├── speed.py
│   │   │   └── fuel_compatibility.py
│   │   │
│   │   ├── evaluation/
│   │   │   ├── evaluator.py
│   │   │   ├── fitness.py
│   │   │   └── penalty.py
│   │   │
│   │   ├── genetic/
│   │   │   ├── population.py
│   │   │   ├── selection.py
│   │   │   ├── crossover.py
│   │   │   ├── mutation.py
│   │   │   ├── repair.py
│   │   │   └── optimizer.py
│   │   │
│   │   └── quantum/
│   │       ├── encoding.py
│   │       ├── state.py
│   │       ├── sampling.py
│   │       ├── update.py
│   │       └── optimizer.py
│   │
│   ├── scenarios/
│   │   ├── scenario.py
│   │   ├── scenario_runner.py
│   │   └── comparison.py
│   │
│   ├── benchmarking/
│   │   ├── runner.py
│   │   ├── metrics.py
│   │   └── statistical_analysis.py
│   │
│   ├── database/
│   │   ├── mongodb.py
│   │   └── repositories/
│   │
│   ├── config/
│   │   └── settings.py
│   │
│   └── utils/
│       ├── logger.py
│       ├── exceptions.py
│       └── helpers.py
│
├── frontend/
│
├── tests/
├── configs/
├── data/
├── models/
├── scripts/
│
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

------------------------------------------------------------------------

# 16. Data Pipeline

The prediction pipeline follows a modular ML workflow.

``` text
Raw Dataset
    |
    v
Data Ingestion
    |
    v
Data Validation
    |
    v
Data Transformation
    |
    v
Feature Engineering
    |
    v
Model Training
    |
    v
Model Evaluation
    |
    v
MLflow Tracking
    |
    v
Best Model
    |
    v
Model Registry
    |
    v
Prediction Service
```

The initial maritime datasets explored for this project include:

-   `cps_poseidon`
-   `cps_triton`
-   `oss_ceto`

Dataset selection and target definition must be finalized during the
data-analysis phase rather than assumed from column names alone.

------------------------------------------------------------------------

# 17. API Design

Initial API endpoints:

``` text
GET  /health

POST /prediction/predict

POST /optimization/run

POST /optimization/compare

POST /scenario/run

POST /benchmark/run

POST /reports/generate

GET  /results/{result_id}
```

### Prediction

``` text
POST /prediction/predict
```

Input:

``` json
{
  "vessel_type": "...",
  "fuel_type": "...",
  "speed": 16,
  "shaft_power": 4200,
  "weather": {}
}
```

Output:

``` json
{
  "predicted_fuel_consumption": 128.4,
  "unit": "kg/h"
}
```

### Optimization

``` text
POST /optimization/run
```

Input contains:

-   Voyage information
-   Fleet configuration
-   Fuel options
-   Objective weights
-   Constraints
-   Algorithm configuration

Output contains:

-   Recommended fleet plan
-   Fuel consumption
-   Cost
-   Emissions
-   Voyage time
-   Constraint status
-   Optimization metadata

------------------------------------------------------------------------

# 18. Technology Stack

  Layer                  Technology
  ---------------------- -------------------------
  Programming Language   Python
  Data Processing        Pandas, NumPy
  ML                     Scikit-learn, XGBoost
  Experiment Tracking    MLflow
  Backend                FastAPI
  Validation             Pydantic
  Database               MongoDB
  Frontend               React + TypeScript
  Visualization          Plotly
  Styling                Tailwind CSS
  Testing                Pytest
  Logging                Python logging / Loguru
  Containerization       Docker
  CI/CD                  GitHub Actions
  Cloud                  AWS
  Initial Deployment     EC2

------------------------------------------------------------------------

# 19. Configuration

Application configuration should not be hard-coded.

Example:

``` text
configs/
├── base.yaml
├── prediction.yaml
├── optimization.yaml
├── scenarios.yaml
└── development.yaml
```

Configuration should control:

-   Dataset paths
-   Model parameters
-   MLflow configuration
-   Database connection
-   Optimizer parameters
-   Objective weights
-   Logging
-   API configuration

------------------------------------------------------------------------

# 20. Logging and Error Handling

All major components should use structured logging.

Example:

``` text
[INFO] Starting prediction pipeline
[INFO] Dataset loaded
[INFO] Validation completed
[INFO] Model loaded
[INFO] Prediction completed

[ERROR] Optimization failed
[ERROR] Invalid vessel configuration
```

Use custom exceptions such as:

``` text
DataValidationError
ModelNotFoundError
InvalidOptimizationProblem
ConstraintViolationError
OptimizationError
ScenarioError
```

API errors should be converted into consistent HTTP responses.

------------------------------------------------------------------------

# 21. Development Workflow

The project should be implemented in this order.

### Phase 1 --- Foundation

``` text
Repository
→ Configuration
→ Logging
→ Exception handling
→ Domain models
```

### Phase 2 --- Data

``` text
Dataset analysis
→ Data ingestion
→ Validation
→ Transformation
→ Feature engineering
```

### Phase 3 --- Prediction

``` text
Baseline models
→ Model training
→ Evaluation
→ MLflow
→ Best model
→ Prediction service
```

### Phase 4 --- Optimization Model

``` text
Decision variables
→ Objectives
→ Constraints
→ Solution representation
→ Evaluator
```

### Phase 5 --- Genetic Algorithm

``` text
Population
→ Selection
→ Crossover
→ Mutation
→ Repair
→ Evaluation
```

### Phase 6 --- Quantum-Inspired Algorithm

``` text
Encoding
→ State representation
→ Sampling
→ Evaluation
→ State update
```

### Phase 7 --- Benchmarking

``` text
GA runs
+
Quantum-Inspired runs
→ Statistical comparison
→ Convergence analysis
→ Scalability analysis
```

### Phase 8 --- Scenario Engine

``` text
Scenario configuration
→ Optimization
→ Result storage
→ Scenario comparison
```

### Phase 9 --- API

``` text
FastAPI
→ Services
→ Prediction
→ Optimization
→ Scenarios
→ Benchmarking
```

### Phase 10 --- Frontend

``` text
Dashboard
→ Prediction UI
→ Optimization UI
→ Scenario UI
→ Benchmark UI
→ Reports
```

### Phase 11 --- Deployment

``` text
Docker
→ AWS
→ CI/CD
→ Monitoring
```

------------------------------------------------------------------------

# 22. Important Design Principles

### 1. Separation of concerns

The API should not contain optimization logic.

``` text
Route
  ↓
Service
  ↓
Domain / Engine
```

### 2. Shared evaluator

GA and Quantum-Inspired algorithms must evaluate solutions using the
same objective and constraint implementation.

### 3. Configuration-driven system

Avoid hard-coded algorithm parameters, database URLs and model paths.

### 4. Replaceable models

The prediction model should be replaceable without changing the API or
optimization engine.

### 5. Reproducibility

Optimization experiments should record:

-   Random seed
-   Algorithm parameters
-   Dataset/model version
-   Scenario configuration
-   Runtime
-   Objective values

### 6. Testability

Each objective, constraint, optimizer operator and service should be
independently testable.

------------------------------------------------------------------------

# 23. Expected End-to-End User Flow

``` text
User
 |
 v
Dashboard
 |
 v
Configure Fleet
 |
 v
Configure Voyage
 |
 v
Select Fuels
 |
 v
Set Objectives
 |
 v
Set Constraints
 |
 v
Select GA / Quantum / Both
 |
 v
Run Optimization
 |
 v
Recommended Fleet Plan
 |
 +------> Compare Algorithms
 |
 +------> Create Scenario
 |             |
 |             v
 |        Re-optimize
 |             |
 |             v
 |        Compare Results
 |
 +------> Generate Report
```

------------------------------------------------------------------------

# 24. Definition of Done

The project is considered functionally complete when a user can:

1.  Configure a fleet.
2.  Configure a voyage.
3.  Specify cargo demand and constraints.
4.  Select available fuels.
5.  Predict fuel consumption.
6.  Run Genetic Algorithm optimization.
7.  Run Quantum-Inspired optimization.
8.  Compare both algorithms.
9.  Create alternative scenarios.
10. Re-optimize scenarios.
11. Visualize fuel, cost and emission results.
12. Verify constraint satisfaction.
13. Generate an optimization report.
14. Access the system through the web UI/API.
15. Run the complete application through Docker.

------------------------------------------------------------------------

# 25. Implementation Philosophy

Do not build the entire application at once.

The recommended dependency chain is:

``` text
DATA
 ↓
PREDICTION
 ↓
MATHEMATICAL MODEL
 ↓
EVALUATOR
 ↓
GA
 ↓
QUANTUM
 ↓
SCENARIOS
 ↓
BENCHMARK
 ↓
API
 ↓
UI
 ↓
DOCKER / AWS
```

The **Evaluator is the central bridge** between the prediction system
and optimization algorithms.

The architecture should allow us to improve any individual component
without rewriting the rest of the platform.
