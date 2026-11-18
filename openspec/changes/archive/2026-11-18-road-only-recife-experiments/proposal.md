# Proposal

## Why

The study already validates symmetric Euclidean CVRP behavior on four classical CVRPLIB benchmark instances (`A-n32-k5`, `A-n45-k6`, `A-n60-k9`, `A-n80-k10`) with known optima, whereas the real-world Recife/PE supply distribution scenario operates exclusively over an asymmetric urban road network (`distance_matrix_road.npy`, where 52.6% of node pairs exhibit directional asymmetry `|D_ij - D_ji| > 0.5 km` up to `3.91 km`, and river/bridge detours reach `4.64x` across the Capibaribe River). Running `Recife-UBS-40-haversine` in Phase 2 or silently falling back to geodesic Haversine distances when the OSRM road matrix is missing or unreachable introduces an idealized symmetric metric that contradicts the road-network study scope.

## What Changes

- **BREAKING** Remove geodesic Haversine distance computation (`compute_haversine_matrix`) and the `mode` parameter / Haversine fallback from `load_recife()` in `src/data/recife_loader.py`; `load_recife(data_dir)` strictly requires the pre-computed OSRM road matrix (`distance_matrix_road.npy`) and raises `FileNotFoundError` when it is absent.
- Remove `haversine_km()` and both Haversine fallback paths (per-cell `None` substitution and full-matrix OSRM failure fallback) from `scripts/prepare_recife_data.py` so dataset preparation fails fast with `RuntimeError` whenever OSRM fails, returns a non-`Ok` status, or returns unreachable (`None`) distance entries.
- Restrict `load_recife_suite()` in `src/experiments/runner.py` to return only `[load_recife(data_dir)]` (`Recife-UBS-40-road`), narrowing Phase 2 from 6 instances to 5 (`A-n32-k5`, `A-n45-k6`, `A-n60-k9`, `A-n80-k10`, and `Recife-UBS-40-road`).
- Update unit tests in `tests/test_data_loading.py`, `tests/test_recife_demand.py`, and `tests/test_experiments.py` to cover strict OSRM road-matrix loading, missing-matrix `FileNotFoundError`, fail-fast OSRM acquisition errors, and road-only Phase 2 suite selection.
- Remove stale tracked Haversine figures (`results/boxplot_Recife-UBS-40-haversine.png`, `results/convergence_Recife-UBS-40-haversine.png`), regenerate Phase 2 outputs in `results/` for the 5-instance suite, and remove all Haversine mode and fallback mentions from `README.md`.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `cvrp-data-loading`: Replace the `Loading the Recife/PE geographic scenario` requirement (which mandated geodesic Haversine fallback) with `Loading the Recife/PE road-network scenario`, strictly requiring the pre-computed OSRM road-network distance matrix and failing explicitly when road distances are unavailable.
- `experiment-benchmarking`: Refine the `Multi-seed and ablation experiment execution` requirement so the default Recife/PE Phase 2 campaign executes exclusively on the road-network instance (`Recife-UBS-40-road`) and excludes `Recife-UBS-40-haversine` from Phase 2 runs, summary tables, statistical tests, and analytical plots.

## Impact

- **Code**: `src/data/recife_loader.py` (remove `compute_haversine_matrix`, `mode`, and Haversine fallback), `scripts/prepare_recife_data.py` (remove `haversine_km` and OSRM-to-Haversine fallbacks), `src/experiments/runner.py` (`load_recife_suite()` returns road-only instance).
- **Tests**: `tests/test_data_loading.py`, `tests/test_recife_demand.py`, `tests/test_experiments.py`.
- **Results**: `results/` (remove `boxplot_Recife-UBS-40-haversine.png` and `convergence_Recife-UBS-40-haversine.png`; regenerate `phase2_results.csv`, `phase2_summary.csv`, `phase2_stats_tests.csv`, `phase2_histories.json`, and `best_solutions.json` for the 5-instance suite).
- **Documentation**: `README.md` (remove all Haversine mode and fallback references across project structure, preprocessing, dataset preparation, Phase 2, and `best_solutions.json` docs).
