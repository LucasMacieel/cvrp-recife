# Spec Delta

## ADDED Requirements

### Requirement: Optional tuned hyperparameter integration in Phase 2 benchmarking
The experiment runner SHALL support running Phase 2 comparison with per-method tuned hyperparameters for Pure GA and Memetic GA either by loading a previously exported HPO configuration file via `--tuned-config <path>` or by executing HPO inline before Phase 2 via `--tune` (with configurable `--hpo-trials` and `--hpo-seeds`). When neither flag is supplied, the runner SHALL preserve its default Phase 1 ablation followed by Phase 2 comparison behavior unchanged.

#### Scenario: Running Phase 2 with a pre-computed tuned configuration file
- **WHEN** the experiment runner is invoked with `--tuned-config <path>` pointing to a valid `hpo_best_configs.json` file
- **THEN** Phase 2 uses the loaded `Pure_GA` and `Memetic_GA` hyperparameter configurations (including each method's operators, population size, rates, tournament size, elitism, and Memetic local search parameters) instead of uniform CLI defaults, and skips Phase 1 operator ablation

#### Scenario: Running inline HPO before Phase 2 via --tune
- **WHEN** the experiment runner is invoked with `--tune`
- **THEN** the runner executes hyperparameter optimization for Pure GA and Memetic GA on the tuning subset, saves HPO artifacts to the output directory, and passes the resulting tuned configurations into Phase 2 comparison

#### Scenario: Rejecting mutually exclusive or invalid tuned configuration inputs
- **WHEN** the experiment runner is invoked with both `--tune` and `--tuned-config`, or with a `--tuned-config` file that is missing or fails schema validation
- **THEN** the runner exits with a clear error message before starting Phase 2

#### Scenario: Default behavior without HPO flags
- **WHEN** the experiment runner is invoked without `--tune` or `--tuned-config`
- **THEN** it executes Phase 1 operator ablation followed by Phase 2 comparison with the default/CLI-specified hyperparameters, maintaining full backward compatibility
