# Tasks

## 1. Static Best-Solution Route Plotter

- [x] 1.1 Implement `plot_best_solution_routes` in `src/experiments/plots.py` supporting geographic (`latlon` with optional OSRM road-snapped polylines via `_fetch_osrm_route_geometry` and straight-line fallback) and Euclidean (`coords`) instances with English labels, and verify via `uv run pytest tests/test_experiments.py -k test_smoke_experiments_plots_and_recife_map`
- [x] 1.2 Add unit tests in `tests/test_experiments.py` covering static PNG export for both `Recife-UBS-40-road` (`use_osrm=False`) and `A-n32-k5` (`coords`), and verify the test passes with `uv run pytest tests/test_experiments.py`

## 2. Runner Integration and Documentation

- [x] 2.1 Wire `plot_best_solution_routes` into `run_post_processing` in `src/experiments/runner.py` to export `best_solution_Recife-UBS-40-road.png` as part of the 4-step post-processing progress pipeline, and verify offline progress and file creation via `uv run pytest tests/test_experiments.py -k test_cli_no_progress_flag_and_post_processing_progress`
- [x] 2.2 Document `best_solution_*.png` and the extended `plots.py` description in `README.md`, and verify the full test suite passes (`uv run pytest`)
- [x] 2.3 Generate `results/best_solution_Recife-UBS-40-road.png` from `results/best_solutions.json` with OSRM road snapping enabled and verify visual consistency with the best Memetic GA routes (`178.40 km`, 8 routes)

## Workflow follow-up

- Review and run `openspec verify` / `openspec archive` when ready to sync the `experiment-benchmarking` delta spec into `openspec/specs/experiment-benchmarking/spec.md`.
