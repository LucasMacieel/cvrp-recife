# Proposal

## Why

The Pure Genetic Algorithm and Memetic Genetic Algorithm currently rely on hardcoded default hyperparameters (`pop_size=60`, `crossover_rate=0.85`, `mutation_rate=0.20`, `tournament_k=3`, `elite_size=2`, `local_search_rate=0.30`, `local_search_max_passes=15`) with only a 4-combination operator ablation in Phase 1. Adding Bayesian hyperparameter optimization (Optuna TPE) allows tuning both Pure GA and Memetic GA systematically and reproducibly, improving solution quality and fairness of comparison without manual trial-and-error.

## What Changes

- Add `optuna` as a runtime dependency in `pyproject.toml` and lock it in `uv.lock`.
- Introduce a standalone hyperparameter optimization module and CLI (`src/experiments/hpo.py`, runnable via `uv run -m src.experiments.hpo`) using Optuna's TPE sampler with deterministic seeding.
- Tune `Pure_GA` and `Memetic_GA` in separate Optuna studies over both operator choices (`crossover`, `mutation`) and numeric hyperparameters (`pop_size`, `crossover_rate`, `mutation_rate`, `tournament_k`, `elite_size`, plus `local_search_rate` and `local_search_max_passes` for Memetic GA) under a configurable generation budget.
- Evaluate each trial across configurable tuning instances (defaulting to the Phase 1 representative subset `A-n32-k5` and `A-n60-k9` to avoid overfitting to the full benchmark suite) and multiple seeds, minimizing mean percentage gap (or normalized distance when no optimum is available).
- Persist tuning outputs to an output directory: best configurations JSON (`hpo_best_configs.json`), per-trial history CSVs (`hpo_trials_pure_ga.csv`, `hpo_trials_memetic_ga.csv`), and summary metrics, with live Rich progress reporting and `--no-progress` support.
- Extend `src/experiments/runner.py` with optional CLI flags:
  - `--tuned-config <path>` to load tuned `Pure_GA` and `Memetic_GA` hyperparameters from JSON for Phase 2 comparison.
  - `--tune` (with configurable `--hpo-trials` and `--hpo-seeds`) to run HPO before Phase 2 and pass the resulting configurations directly into Phase 2.
- Keep existing default `runner.py` behavior unchanged when neither `--tuned-config` nor `--tune` is passed.

## Capabilities

### New Capabilities
- `hyperparameter-optimization`: Automated Optuna-based hyperparameter tuning for Pure GA and Memetic GA, including search space definition, multi-instance/multi-seed objective evaluation, deterministic seeding, Rich progress reporting, and JSON/CSV artifact export.

### Modified Capabilities
- `experiment-benchmarking`: Support loading tuned Pure GA and Memetic GA hyperparameter configurations (via `--tuned-config` or `--tune`) in the Phase 2 comparison campaign and recording the full tuned configuration while preserving backward-compatible default behavior.
- `python-environment`: Include `optuna` in the required runtime dependencies declared in `pyproject.toml` and locked in `uv.lock`.

## Impact

- **Dependencies**: Adds `optuna` to `pyproject.toml` and updates `uv.lock`.
- **New Code**: `src/experiments/hpo.py`, HPO progress helpers in `src/experiments/progress.py`, and unit/smoke tests in `tests/test_hpo.py`.
- **Modified Code**: `src/experiments/runner.py` (accepting per-method `GAConfig` overrides in `run_phase2_comparison` and optional CLI flags `--tuned-config`, `--tune`, `--hpo-trials`, `--hpo-seeds`), `README.md` (documenting HPO usage).
- **Compatibility**: Fully backward compatible; existing `runner.py` invocations and `GAConfig` defaults remain unchanged.
