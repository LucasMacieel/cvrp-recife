# Design

## Context

See `proposal.md` for motivation and scope. Currently:
- `src/solver/genetic.py` defines a frozen dataclass `GAConfig` with 12 fields (`pop_size`, `generations`, `crossover_rate`, `mutation_rate`, `tournament_k`, `elite_size`, `crossover`, `mutation`, `memetic`, `local_search_rate`, `local_search_max_passes`, `seed`).
- `src/experiments/runner.py` runs Phase 1 operator ablation on `[A-n32-k5, A-n60-k9]` for `Pure_GA` only, then passes a single `(crossover, mutation)` pair and scalar CLI defaults (`pop_size`, `generations`, `ls_rate`) to `run_phase2_comparison` for both `Pure_GA` and `Memetic_GA`.
- `src/experiments/progress.py` provides Rich progress bars and summary tables for Phase 1, Phase 2, and post-processing.
- Dependencies are managed exclusively via `pyproject.toml` and `uv.lock`.

## Goals / Non-Goals

**Goals:**
- Provide a clean, reproducible Optuna TPE hyperparameter optimization module (`src/experiments/hpo.py`) usable both programmatically and via `uv run -m src.experiments.hpo`.
- Tune `Pure_GA` and `Memetic_GA` independently over their respective search spaces (including categorical operators and numeric parameters).
- Support loading tuned configs into `src/experiments/runner.py` (`--tuned-config`) or running HPO inline (`--tune`) without breaking existing CLI flags, function signatures, or tests.
- Integrate with `src/experiments/progress.py` for live trial telemetry and end-of-HPO summary tables, honoring `--no-progress`.

**Non-Goals:**
- Tuning `generations` as a search variable (varying generations unfairly favors larger budgets; `generations` remains a fixed configurable budget parameter).
- Distributed multi-node Optuna RDB storage (in-memory studies with JSON/CSV export are sufficient for this project's scale).
- Modifying the core GA/Memetic solver algorithm or `GAConfig` default values.
- Tuning on the Recife road-network instance by default (default tuning uses the CVRPLIB representative subset `[A-n32-k5, A-n60-k9]` to avoid overfitting to the target case study).

## Decisions

### 1. Optuna TPE Sampler with Deterministic Seeding
- **Decision**: Use `optuna.create_study(direction="minimize", sampler=optuna.samplers.TPESampler(seed=hpo_seed))` and silence Optuna's verbose default logger (`optuna.logging.set_verbosity(optuna.logging.WARNING)`) so Rich progress bars render cleanly.
- **Rationale**: TPE handles mixed categorical + integer + continuous search spaces well with small trial budgets (e.g., 20–50 trials) and is deterministic when seeded and run sequentially.
- **Alternatives considered**: Dependency-free random/Sobol search (less sample-efficient for 7–9 parameters); grid search (combinatorial explosion).

### 2. Search Space Bounds & Parameter Constraints
- **Decision**: Define separate search spaces for `Pure_GA` and `Memetic_GA` with fixed `generations` (default `100` for standalone HPO, configurable via `--generations`):
  - Shared parameters:
    - `crossover`: categorical `["OX", "PMX"]`
    - `mutation`: categorical `["Swap", "Inversion"]`
    - `pop_size`: int `[30, 120]`, step `10`
    - `crossover_rate`: float `[0.60, 0.98]`
    - `mutation_rate`: float `[0.05, 0.50]`
    - `tournament_k`: int `[2, 6]`
    - `elite_size`: int `[1, 6]`
  - Memetic-only parameters (`memetic=True`):
    - `local_search_rate`: float `[0.10, 0.60]`
    - `local_search_max_passes`: int `[5, 25]`, step `5`
- **Rationale**: Since `min(pop_size) = 30` and `max(elite_size) = max(tournament_k) = 6`, the invariants `elite_size < pop_size` and `tournament_k <= pop_size` are always satisfied by construction without dynamic conditional bounds.
- **Validation**: When loading a config JSON file, explicitly validate all fields (`crossover` in `CROSSOVER_OPERATORS`, `mutation` in `MUTATION_OPERATORS`, `1 <= elite_size < pop_size`, `2 <= tournament_k <= pop_size`, rates in `[0.0, 1.0]`, `local_search_max_passes >= 1`).

### 3. Normalized Multi-Instance Objective Function
- **Decision**: For each trial, evaluate the candidate `GAConfig` over every `(instance, seed)` pair in `instances x seeds`. Compute per-instance normalized score:
  - If `instance.optimal_value` is defined and positive: `compute_gap_pct(res.distance, instance.optimal_value)`.
  - Otherwise (e.g., if a user explicitly tunes on Recife): `((res.distance - greedy_dist) / greedy_dist) * 100.0` where `greedy_dist` is precomputed once per instance via `solve_greedy(instance).distance`.
  - Trial objective = arithmetic mean of normalized scores across all `(instance, seed)` runs.
- **Rationale**: Raw distances vary by orders of magnitude across instances (e.g., `A-n32-k5` ~784 vs `A-n80-k10` ~1763 vs Recife road meters ~80,000+). Normalizing each instance to a percentage gap gives every tuning instance equal weight.

### 4. Artifact Schema (`hpo_best_configs.json` & Trial CSVs)
- **Decision**:
  - `hpo_best_configs.json`:
    ```json
    {
      "metadata": {
        "instances": ["A-n32-k5", "A-n60-k9"],
        "seeds": [1, 2, 3],
        "n_trials": 30,
        "generations": 100,
        "hpo_seed": 42
      },
      "Pure_GA": {
        "best_objective": 12.34,
        "best_trial_number": 17,
        "config": {
          "pop_size": 80,
          "crossover_rate": 0.90,
          "mutation_rate": 0.25,
          "tournament_k": 4,
          "elite_size": 2,
          "crossover": "OX",
          "mutation": "Inversion",
          "memetic": false
        }
      },
      "Memetic_GA": {
        "best_objective": 1.85,
        "best_trial_number": 24,
        "config": {
          "pop_size": 60,
          "crossover_rate": 0.85,
          "mutation_rate": 0.20,
          "tournament_k": 3,
          "elite_size": 2,
          "crossover": "OX",
          "mutation": "Inversion",
          "memetic": true,
          "local_search_rate": 0.35,
          "local_search_max_passes": 15
        }
      }
    }
    ```
  - `hpo_trials_pure_ga.csv` / `hpo_trials_memetic_ga.csv`: columns `trial_number`, `state`, `objective`, `duration_sec`, plus all sampled hyperparameters for that method.
- **Rationale**: Storing `config` without `generations` or `seed` lets Phase 2 apply its own `--generations` budget and Phase 2 seed list (`1..30`) cleanly, while still recording the tuning `generations` in `metadata`.

### 5. `runner.py` Integration & Backward Compatibility
- **Decision**:
  - Extend `run_phase2_comparison` with optional keyword-only parameters `pure_ga_config: GAConfig | None = None` and `memetic_ga_config: GAConfig | None = None`. When provided, each method uses its own `GAConfig` (with `seed` replaced per run via `dataclasses.replace`, and `generations` overridden by the Phase 2 `generations` argument). When `None`, `run_phase2_comparison` builds `GAConfig` identically to today.
  - Add CLI flags to `runner.py`:
    - `--tuned-config <path>` (Path to `hpo_best_configs.json`)
    - `--tune` (boolean flag to run HPO before Phase 2)
    - `--hpo-trials` (int, default `25`)
    - `--hpo-seeds` (int, default `3`)
    - `--hpo-generations` (int | None, default `None` -> uses `--generations`)
    - `--hpo-seed` (int, default `42`)
  - Make `--tune` and `--tuned-config` mutually exclusive via `parser.add_mutually_exclusive_group()`.
  - When `--tuned-config` or `--tune` is used, skip Phase 1 operator ablation (since operators are already selected per method by HPO) and proceed directly to Phase 2 with the tuned per-method configs.
  - Record each method's actual `crossover` and `mutation` in Phase 2 CSV rows (`_make_row`) so `phase2_results.csv` and `phase2_summary.csv` accurately reflect method-specific tuned operators.
- **Rationale**: Preserves 100% backward compatibility with existing callers and tests while making tuned benchmarking ergonomic.

## Risks / Trade-offs

- **[Wall-clock runtime of HPO]** → Memetic GA trials with large `pop_size` and high `local_search_rate` can be slow. Mitigation: Default HPO uses 2 representative instances (`A-n32-k5`, `A-n60-k9`), 3 seeds, and 25–30 trials with live Rich progress showing elapsed time, ETA, and best objective so users can size budgets appropriately.
- **[Overfitting hyperparameters to tuning instances]** → Mitigation: Keep `A-n45-k6`, `A-n80-k10`, and `Recife-UBS-40-road` out of the default tuning set so Phase 2 still evaluates generalization on unseen instances.
- **[Optuna logging interfering with Rich progress bars]** → Mitigation: Suppress Optuna INFO logs during optimization and route all progress/summary output through the shared Rich `Console`.
