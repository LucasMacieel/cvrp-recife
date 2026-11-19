# Tasks

## 1. Environment & Dependency Setup

- [x] 1.1 Add `optuna` to runtime dependencies in `pyproject.toml` and update `uv.lock` via `uv lock` / `uv sync`; verify `uv sync --frozen` succeeds and `uv run python -c "import optuna; print(optuna.__version__)"` exits 0

## 2. Core HPO Engine & Artifact Persistence

- [x] 2.1 Create `src/experiments/hpo.py` with search space sampling (`Pure_GA` and `Memetic_GA`), normalized multi-instance/multi-seed objective evaluation (using `optimal_value` gap% when known and Greedy baseline normalization otherwise), and seeded `TPESampler` optimization (`optimize_ga`, `run_hpo_suite`); verify unit tests in `tests/test_hpo.py` confirm valid parameter bounds, objective calculation (with and without `optimal_value`), and deterministic reproducibility across identical seeds
- [x] 2.2 Implement `hpo_best_configs.json` serialization/deserialization with schema and parameter validation (`save_hpo_results`, `load_tuned_configs`) plus per-trial CSV export (`hpo_trials_pure_ga.csv`, `hpo_trials_memetic_ga.csv`); verify unit tests in `tests/test_hpo.py` cover round-trip JSON loading, CSV schema, and rejection of invalid or missing config files
- [x] 2.3 Add HPO Rich progress formatting and summary table helpers to `src/experiments/progress.py` and integrate live trial telemetry, summary rendering, and `--no-progress` handling into `src/experiments/hpo.py` CLI (`build_arg_parser`, `main`); verify tests in `tests/test_hpo.py` confirm `uv run -m src.experiments.hpo --help`, `--method pure|memetic|both`, and identical artifact output with `--no-progress`

## 3. Experiment Runner Integration & Documentation

- [x] 3.1 Extend `run_phase2_comparison` in `src/experiments/runner.py` to accept optional `pure_ga_config: GAConfig | None` and `memetic_ga_config: GAConfig | None` overrides (applying Phase 2 `generations` and per-run `seed`, and logging each method's actual `crossover`/`mutation` in result rows); verify unit tests in `tests/test_experiments.py` confirm method-specific configs are used while default calls remain backward compatible
- [x] 3.2 Add mutually exclusive `--tuned-config <path>` and `--tune` CLI flags (plus `--hpo-trials`, `--hpo-seeds`, `--hpo-generations`, `--hpo-seed`) to `src/experiments/runner.py` so tuned runs skip Phase 1 ablation and pass tuned configs to Phase 2; verify tests in `tests/test_experiments.py` cover `--tuned-config`, `--tune`, mutual-exclusion error handling, and default unchanged behavior
- [x] 3.3 Document standalone HPO usage (`uv run -m src.experiments.hpo`) and runner integration (`--tuned-config`, `--tune`) in `README.md`; verify the documented `--help` commands execute cleanly as written

## 4. End-to-End Integration Verification

- [x] 4.1 Run the full test suite (`uv run pytest`) and a fast end-to-end smoke campaign (`uv run -m src.experiments.hpo --trials 2 --seeds 1 --generations 5 --no-progress` followed by `uv run -m src.experiments.runner --tuned-config ... --phase2-seeds 1 --generations 5 --no-progress`) to verify all tests pass and all HPO + Phase 2 artifacts are generated cleanly
