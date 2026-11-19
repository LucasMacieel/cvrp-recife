# Spec Delta

## Purpose

Provides reproducible Bayesian hyperparameter optimization for both the Pure Genetic Algorithm and Memetic Genetic Algorithm CVRP solvers, tuning operator selections and numeric parameters independently and exporting reusable best-configuration artifacts and trial histories.

## ADDED Requirements

### Requirement: Separate hyperparameter optimization for Pure GA and Memetic GA
The system SHALL support optimizing hyperparameters for Pure GA (`memetic=False`) and Memetic GA (`memetic=True`) in separate optimization runs over both categorical operator choices (`crossover` in `{OX, PMX}`, `mutation` in `{Swap, Inversion}`) and numeric parameters (`pop_size`, `crossover_rate`, `mutation_rate`, `tournament_k`, `elite_size`, plus `local_search_rate` and `local_search_max_passes` for Memetic GA) while holding the generation budget fixed to a configurable value.

#### Scenario: Tuning both methods via standalone CLI
- **WHEN** a user invokes the standalone HPO CLI with a target trial count, seed count, and generation budget
- **THEN** the system executes an optimization run for Pure GA and a separate optimization run for Memetic GA, respecting valid hyperparameter bounds (including `elite_size < pop_size` and `tournament_k <= pop_size`), and produces a distinct best configuration for each method

#### Scenario: Tuning a single selected method
- **WHEN** a user restricts the HPO CLI to only `pure` or only `memetic`
- **THEN** the system executes optimization exclusively for the selected method and writes only that method's trial history and best configuration entry

### Requirement: Multi-instance and multi-seed objective evaluation
The system SHALL evaluate each candidate hyperparameter configuration across a configurable list of CVRP tuning instances (defaulting to a representative subset of CVRPLIB instances rather than the full evaluation suite) and multiple deterministic random seeds, minimizing the mean normalized objective across all `(instance, seed)` evaluations.

#### Scenario: Objective aggregation on instances with known optima
- **WHEN** a trial is evaluated on instances that define positive known optimal values
- **THEN** the trial objective equals the mean percentage gap `((distance - optimal_value) / optimal_value) * 100` across all evaluated instances and seeds

#### Scenario: Objective aggregation when an instance lacks a known optimum
- **WHEN** a trial is evaluated on an instance whose `optimal_value` is `None`
- **THEN** the system normalizes the instance's obtained distance against a deterministic reference (such as the Greedy baseline distance for that instance) so instances of different scales contribute comparably to the trial objective

### Requirement: Deterministic reproducibility of hyperparameter search
The system SHALL support a configurable HPO master seed that controls both the hyperparameter sampler and the evaluation seed list so repeated tuning runs with identical arguments produce identical trial sequences and best configurations.

#### Scenario: Reproducible HPO run with fixed seed
- **WHEN** hyperparameter optimization is executed twice with the same instances, trial count, generation budget, evaluation seeds, and master seed
- **THEN** both runs evaluate the exact same hyperparameter configurations in the same order and select identical best configurations and objective values

### Requirement: Persisted HPO artifacts and live progress reporting
The system SHALL export the best tuned configurations to a JSON file (`hpo_best_configs.json`), export complete per-trial histories to CSV files (`hpo_trials_pure_ga.csv` and/or `hpo_trials_memetic_ga.csv`), display live progress and summary tables during optimization, and support suppressing live progress output via `--no-progress` without changing exported artifacts.

#### Scenario: Exporting best configs and trial history
- **WHEN** hyperparameter optimization completes for Pure GA and Memetic GA
- **THEN** the output directory contains `hpo_best_configs.json` with validated hyperparameter dictionaries, objective values, and metadata (instances, seeds, trials, generations), plus per-trial CSV files containing trial number, state, objective value, duration, and all sampled hyperparameters

#### Scenario: Disabling live progress output
- **WHEN** the HPO CLI is invoked with `--no-progress`
- **THEN** live progress bars and summary tables are suppressed while all JSON and CSV output artifacts are written identically
