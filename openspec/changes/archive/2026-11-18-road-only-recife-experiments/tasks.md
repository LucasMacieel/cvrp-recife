# Tasks

## 1. Strict OSRM Road-Only Data Loading & Preparation

- [x] 1.1 Remove `compute_haversine_matrix()`, the `mode` parameter, and the Haversine fallback from `src/data/recife_loader.py` so `load_recife(data_dir)` strictly loads `distance_matrix_road.npy` and raises `FileNotFoundError` when missing; update `tests/test_data_loading.py` (road-only assertion, missing-matrix `FileNotFoundError` test, and a `3 x 3` `distance_matrix_road.npy` fixture for `test_load_recife_enriched_demand_metadata_offline`) and verify `pytest tests/test_data_loading.py` passes.
- [x] 1.2 Remove `haversine_km()` and both Haversine fallback paths (per-cell `None` substitution and full-matrix fallback) from `scripts/prepare_recife_data.py` so `_fetch_osrm_matrix()` raises `RuntimeError` on request errors, non-`Ok` responses, or `None` distance entries; add unit tests in `tests/test_recife_demand.py` verifying fail-fast behavior on OSRM errors and unreachable `None` cells, and verify `pytest tests/test_recife_demand.py` passes.

## 2. Road-Only Experiment Runner & Tests

- [x] 2.1 Update `load_recife_suite()` and Phase 2 comments/docstrings in `src/experiments/runner.py` to return `[load_recife(data_dir)]`, update `load_recife(...)` call sites in `tests/test_experiments.py`, add a unit test verifying `load_recife_suite("data/recife_ubs")` returns a single instance named `Recife-UBS-40-road` with `is_symmetric is False`, and run `pytest` to confirm the full test suite passes.

## 3. Results Cleanup, Regeneration & Documentation

- [x] 3.1 Remove stale `results/boxplot_Recife-UBS-40-haversine.png` and `results/convergence_Recife-UBS-40-haversine.png`, regenerate Phase 1/2 results via `python -m src.experiments.runner`, and verify `results/phase2_results.csv`, `results/phase2_summary.csv`, `results/phase2_stats_tests.csv`, `results/phase2_histories.json`, and `results/best_solutions.json` contain only the 5 instances (`A-n32-k5`, `A-n45-k6`, `A-n60-k9`, `A-n80-k10`, `Recife-UBS-40-road`) with zero `Recife-UBS-40-haversine` entries, exactly 5 boxplot PNGs and 5 convergence PNGs exist, and `results/recife_map.html` retains road-snapped polylines.
- [x] 3.2 Update `README.md` to remove all Haversine mode and Haversine fallback mentions across project structure, preprocessing, dataset preparation, Phase 2 execution, and `best_solutions.json` docs, and verify no Haversine references remain in `README.md`.
