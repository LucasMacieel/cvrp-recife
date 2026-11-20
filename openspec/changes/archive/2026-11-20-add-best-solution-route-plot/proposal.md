# Proposal

## Why

Phase 2 post-processing previously generated static convergence curves (`convergence_*.png`), comparative boxplots (`boxplot_*.png`), and an interactive Folium HTML map (`recife_map.html`), but lacked a reproducible static Matplotlib plot of the best vehicle routes (`best_solution_<instance>.png`). Adding a dedicated static best-solution route plotter to the repository closes this reproducibility gap so publication-ready route figures can be generated directly by the automated experiment pipeline.

## What Changes

- Add `plot_best_solution_routes` to `src/experiments/plots.py` to render static Matplotlib PNG visualizations of CVRP vehicle routes with English labels, supporting both geographic (`latlon`, with optional OSRM road-snapped polylines via `_fetch_osrm_route_geometry` and straight-line fallback) and Euclidean (`coords`) instances.
- Wire `plot_best_solution_routes` into `run_post_processing` in `src/experiments/runner.py` to export `best_solution_Recife-UBS-40-road.png` for the best `Memetic_GA` solution alongside the convergence curves, comparative boxplots, and interactive Recife HTML map.
- Update `README.md` to document `best_solution_*.png` and the extended `plots.py` module.
- Extend `tests/test_experiments.py` to verify static best-solution route plot generation for both geographic (offline fallback) and Euclidean instances as well as the 4-step post-processing workflow.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `experiment-benchmarking`: Extend `Analytical chart and interactive Recife map generation` to include static best-solution route plotting (`best_solution_<instance>.png`) with road-snapped OSRM geometry and graceful straight-line fallback, and update the `Post-processing progress feedback` scenario under `Phase 1 (HPO) and Phase 2 progress reporting and summaries` to include the best-solution route plotting step.

## Impact

- **Code**: `src/experiments/plots.py` (`plot_best_solution_routes`), `src/experiments/runner.py` (`run_post_processing`).
- **Tests**: `tests/test_experiments.py` (smoke tests for geographic/Euclidean route plots and post-processing progress/artifact verification).
- **Documentation**: `README.md` (project structure and `results/` output listing).
- **Artifacts**: `results/best_solution_Recife-UBS-40-road.png`.
- **Dependencies**: Reuses existing `matplotlib` and `src.experiments.map_recife._fetch_osrm_route_geometry` (`requests`); no new dependencies required.
