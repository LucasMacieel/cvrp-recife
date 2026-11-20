# Proposal

## Why

The three CVRPLIB benchmark instances (`A-n32-k5`, `A-n45-k6`, `A-n60-k9`) ship with published global optima, enabling exact percentage optimality gap reporting and reference lines in benchmark plots. By contrast, our custom real-world held-out scenario (`Recife-UBS-40-road`, 40 health units with an asymmetric OSRM road-network distance matrix) currently lacks a proven optimum, so `phase2_results.csv`, `phase2_summary.csv`, and `boxplot_Recife-UBS-40-road.png` cannot quantify how close the Greedy, Pure GA, and Memetic GA algorithms are to the true global minimum.

## What Changes

- Add an optional `exact` dependency group to `pyproject.toml` (locked in `uv.lock`) containing `ortools` (Google OR-Tools CP-SAT with built-in `AddMultipleCircuit` and exact cumulative load propagation) so the core Computational Intelligence runtime environment remains lightweight and portable while exact solves remain simple, fast, and reproducible via `uv run --group exact`.
- Add a reproducible offline exact-solver script (`scripts/solve_recife_exact.py`) that:
  - Validates exactness against `A-n32-k5` (`optimal_value == 784.0`) as a built-in ground-truth check.
  - Solves `Recife-UBS-40-road` as a directed Asymmetric CVRP (ACVRP) with capacity `Q = 100` and unconstrained fleet size (`K >= 7`), matching the feasibility rules of `src/solver/decoder.py`.
  - Independently verifies the returned routes against `validate_routes()` and `total_distance()`.
  - Persists the proven `optimal_value` and a reproducible `exact_solution` certificate (routes, dual lower bound, solver version, runtime, and distance-matrix SHA-256 hash) into `data/recife_ubs/recife_ubs.json`.
- Update `src/data/recife_loader.py` (`load_recife`) to read the optional `optimal_value` field from `recife_ubs.json` into `CVRPInstance` while staying 100% offline and backward-compatible when the field is absent.
- Keep the exact solver strictly out of the Phase 1/Phase 2 experiment runner (`src/experiments/runner.py`) so the CI comparison remains focused on `Greedy`, `Pure_GA`, and `Memetic_GA`.
- Refresh the existing Phase 2 benchmark artifacts (`results/phase2_results.csv`, `results/phase2_summary.csv`, `results/phase2_stats_tests.csv`, `results/phase2_histories.json`, `results/best_solutions.json`, and plots) using the existing `--tuned-config results/hpo_best_configs.json` so `Recife-UBS-40-road` includes its proven optimality gap and `Optimal` boxplot reference line.

## Capabilities

### New Capabilities
<!-- None: extends existing dataset preparation/loading and Python environment capabilities. -->

### Modified Capabilities
- `cvrp-data-loading`: Extend Recife/PE static dataset preparation and offline loading to support computing, verifying, persisting, and loading a certified exact `optimal_value` (and `exact_solution` provenance metadata) for `Recife-UBS-40-road`.
- `python-environment`: Extend `pyproject.toml` and `uv.lock` dependency management to declare an optional `exact` dependency group for offline exact-solver reproducibility without adding native solver binaries to the default runtime dependencies.

## Impact

- **Dependencies**: `pyproject.toml` (`[dependency-groups]` `exact`) and `uv.lock`. Default `uv sync --no-dev` and `uv sync --frozen` runtime behavior remains unchanged.
- **Scripts & Data**: New `scripts/solve_recife_exact.py`; updated `data/recife_ubs/recife_ubs.json` with `optimal_value` and `exact_solution` certificate.
- **Core Code**: Minor update in `src/data/recife_loader.py` (passes optional `optimal_value` into `CVRPInstance`); no changes required in `src/experiments/runner.py`, `src/experiments/stats.py`, `src/experiments/progress.py`, or `src/experiments/plots.py` because they already consume `instance.optimal_value`.
- **Tests & Results**: New unit tests covering `load_recife` optimal-value loading and exact-certificate validation; refreshed `results/` Phase 2 tables and plots.
