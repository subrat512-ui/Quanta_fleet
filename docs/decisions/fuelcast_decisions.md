# FuelCast Approved Decisions

Agents must not silently reverse these decisions. Propose any change with its
reason, migration impact and affected tests before implementation.

| ID | Decision | Rationale |
| --- | --- | --- |
| D001 | Dataset is `krohnedigital/FuelCast` on Hugging Face. | Provides one authoritative, documented source. |
| D002 | Use configurations `cps_poseidon`, `cps_triton`, `oss_ceto`. | They are the three published ship configurations. |
| D003 | Use six raw features listed in the master specification. | Keeps the baseline small and VQR feasible. |
| D004 | Target is `Consumer_Total_MomentaryFuel`, renamed `fuel_consumption_kg_s`. | Published total fuel target with explicit kg/s units. |
| D005 | Exclude component fuel, power, RPM and torque. | Prevents leakage and defines an operational/environment baseline. |
| D006 | `vessel_id` and `time_index` are metadata, not v1 features. | Prevents simple vessel memorization and preserves splitting/reporting. |
| D007 | Split 70/15/15 chronologically within each vessel. | Avoids leakage between adjacent five-minute observations. |
| D008 | ETL never imputes the target or model features. | Target errors are removed; feature imputation is training-only. |
| D009 | MongoDB and training consume the same canonical file version. | Makes training reproducible and independent of mutable DB state. |
| D010 | Validation MAE chooses models; test is used once after freezing. | Prevents test-set leakage. |
| D011 | Classical candidates are Ridge, RF, GB and XGBoost initially. | Useful bounded comparison without model sprawl. |
| D012 | QPSO-SVR is labelled quantum-inspired/classical. | QPSO tunes a classical SVR and uses no quantum hardware. |
| D013 | VQR is the genuine quantum candidate and starts on a simulator. | Technically honest, reproducible prototype. |
| D014 | One authoritative orchestrator replaces competing paths. | Prevents incompatible pipeline contracts. |
| D015 | One writer per phase; parallel agents are read-only. | Avoids shared-worktree conflicts. |
| D016 | Phase 5 uses saved Phase 4 training/validation arrays and explicit single validation scoring. | Prevents a new random split, preprocessing refit, and test-based tuning. |
| D017 | Quick mode samples training rows deterministically by vessel; validation remains complete. | Bounds smoke-run cost without changing shared row identities. |
| D018 | XGBoost is pinned to 3.2.0 for the Python 3.11 project environment. | The originally planned 3.4.1 requires Python 3.12; macOS also needs the OpenMP runtime. |
| D019 | Phase 7 uses the six saved Phase 4 VQR angles without refitting their scaler. | Five features are bounded in `[0, pi]`; wind direction is a direct periodic angle in `[0, 2pi]`. No Phase 4 migration is needed. |
| D020 | Initial VQR has six `RY` input rotations, one linear-CX `real_amplitudes` repetition, 12 weights and the mean single-qubit Z observable. | The shallow six-qubit circuit includes feature interactions through CX gates and has a bounded expectation output. |
| D021 | VQR uses exact `QMLEstimator`, scaled-target squared error and COBYLA with deterministic initial weights. | Simulator execution is reproducible and does not imply real-hardware use or quantum advantage. SciPy 1.17.1 enforces at least 14 COBYLA evaluations for 12 weights, so quick mode uses 14 rather than the originally proposed 5; normal remains 80. |
| D022 | VQR fitting samples 60 quick or 600 normal training rows proportionally and evenly by vessel; both modes score the complete saved validation partition. | Bounds fitting cost, preserves the shared validation identities and keeps the test partition untouched. Quick metrics are smoke evidence only. |
| D023 | VQR depends optionally on Qiskit 2.5.2 and Qiskit Machine Learning 0.9.1. | V2 exact statevector primitives and QML optimizers need neither Aer nor `qiskit-algorithms`; ordinary non-quantum tests remain usable without quantum packages. |
| D024 | Phase 8 chooses among four normal-mode classical candidates and normal-mode VQR by the lowest recalculated validation MAE, with candidate-name tie breaks. | Quick modes are smoke evidence and QPSO-SVR is deferred; test metrics cannot alter the champion. |
| D025 | The Phase 8 champion reuses the verified saved model with `refit: false`. | A frozen model and training-fitted preprocessing make the one final test reproducible across families. |

## Open decisions

- Exact dataset revision pin/fingerprint representation.
