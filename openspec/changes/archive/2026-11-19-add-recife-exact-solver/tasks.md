# Tasks

## 1. Environment & Dependency Group Setup

- [x] 1.1 Add the optional `exact` dependency group (`exact = ["ortools>=9.11"]`) under `[dependency-groups]` in `pyproject.toml`, update `uv.lock`, and verify both `uv sync --frozen --no-dev` (core runtime without `exact`) and `uv run --group exact python -c "from ortools.sat.python import cp_model"` succeed.

## 2. Recife Loader Optimal-Value Support

- [x] 2.1 Update `load_recife()` in `src/data/recife_loader.py` to read optional `optimal_value` from `recife_ubs.json` (converting non-null values to `float` and preserving `None` when absent) and pass it to `CVRPInstance`; verify with `uv run pytest tests/test_data_loading.py`.
- [x] 2.2 Add unit tests in `tests/test_data_loading.py` covering `load_recife()` with a positive `optimal_value`, with `optimal_value` omitted/`null`, and with an invalid non-positive `optimal_value`; verify `uv run pytest tests/test_data_loading.py` passes.

## 3. Offline Exact ACVRP Solver Script

- [x] 3.1 Implement `scripts/solve_recife_exact.py` with a CLI (`--data-dir`, `--time-limit`, `--upper-bound`, `--skip-self-check`, `--dry-run`) that models directed ACVRP with unconstrained fleet size (`K >= ceil(sum(demands)/capacity)`), runs a ground-truth self-check on `A-n32-k5` (`== 784.0`), independently verifies routes via `validate_routes()` and `total_distance()` (`<= 1e-4` tolerance), computes `distance_matrix_road.npy` SHA-256, and writes `optimal_value` + `exact_solution` to `recife_ubs.json` only when global optimality is proven; verify `uv run --group exact scripts/solve_recife_exact.py --help` exits 0.
- [x] 3.2 Add unit tests (e.g., `tests/test_exact_solver.py`) verifying exact-solution certificate validation, dry-run non-mutation, refusal to write `optimal_value` on unproven status, and matrix SHA-256 provenance without requiring the optional `exact` solver group during standard `uv run pytest`; verify `uv run pytest tests/test_exact_solver.py` passes.
- [x] 3.3 Document the `uv run --group exact scripts/solve_recife_exact.py` offline reproduction command and note that regenerating the Recife dataset via `prepare_recife_data.py` clears `optimal_value` in `README.md`; verify the documented CLI invocation matches `--help`.

## 4. Compute Proven Recife Optimum & Refresh Benchmark Results

- [x] 4.1 Run `uv run --group exact scripts/solve_recife_exact.py` to verify `A-n32-k5 == 784.0`, prove global optimality on `Recife-UBS-40-road`, and persist `optimal_value` and `exact_solution` into `data/recife_ubs/recife_ubs.json`; verify `load_recife().optimal_value` matches the certified distance and `validate_routes()` passes on the saved routes.
- [x] 4.2 Refresh Phase 2 benchmark results and plots via `uv run -m src.experiments.runner --tuned-config results/hpo_best_configs.json` and verify `results/phase2_results.csv`, `results/phase2_summary.csv`, and `results/boxplot_Recife-UBS-40-road.png` include populated `optimal_value` and `gap_pct` entries for `Recife-UBS-40-road`.
- [x] 4.3 Run the full regression suite (`uv run pytest`) and confirm all tests pass without requiring `--group exact`.
