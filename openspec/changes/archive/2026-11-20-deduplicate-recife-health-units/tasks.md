# Tasks

## 1. Cross-Dataset Deduplication & Unique Node IDs

- [x] 1.1 Refactor `scripts/prepare_recife_data.py` to extract `select_recife_nodes(ubs_rows, usf_rows, target_customers=40)` with multi-key cross-dataset deduplication (canonical `US <number>` code, valid non-placeholder CNES, normalized `(name, bairro)`, and `(round(lat, 5), round(lon, 5))`), deterministic unique ID generation for missing/placeholder CNES values, and post-selection integrity validation; verify with `uv run pytest tests/test_recife_demand.py`.
- [x] 1.2 Add unit tests in `tests/test_recife_demand.py` covering shifted-coordinate `US` code duplicates (reproducing `US 155`, `US 121`, `US 137`), valid CNES duplicates, normalized `(name, bairro)` duplicates, distinct nearby facilities (~45 m apart) remaining separate, and multiple distinct units with placeholder CNES (`9999999` / `0000000`) receiving unique IDs; verify all new tests pass via `uv run pytest tests/test_recife_demand.py`.
- [x] 1.3 Update `src/data/recife_loader.py` (`load_recife`) to reject `recife_ubs.json` payloads containing duplicate node `id` values with a descriptive `ValueError`, and add a corresponding unit test in `tests/test_data_loading.py`; verify via `uv run pytest tests/test_data_loading.py`.

## 2. Dataset Regeneration & Exact Optimum Re-Certification

- [x] 2.1 Run `uv run python scripts/prepare_recife_data.py` to regenerate `data/recife_ubs/recife_ubs.json` and `data/recife_ubs/distance_matrix_road.npy`, and verify via a quick Python check that the regenerated file contains 41 nodes (1 depot + 40 customers), 41 unique node `id` values, zero duplicate canonical `US` codes, and no `USF-9999999` entries.
- [x] 2.2 Run `uv run --group exact python scripts/solve_recife_exact.py` to prove global optimality (`gap == 0%`) on the deduplicated `Recife-UBS-40-road` instance and persist the updated `optimal_value` and `exact_solution` certificate (including matching `distance_matrix_sha256`) into `data/recife_ubs/recife_ubs.json`; verify exit code 0 and `[CERTIFIED]` output.
- [x] 2.3 Update `tests/test_data_loading.py` (`test_load_recife_road_only`) with the newly certified `optimal_value` and assertions that `data/recife_ubs/recife_ubs.json` has 41 unique node `id`s and zero duplicate canonical `US` codes; verify via `uv run pytest`.

## 3. Downstream Benchmark Refresh & Final Verification

- [x] 3.1 Refresh Phase 2 benchmark results, statistical tests, route plots, and Recife map in `results/` against the deduplicated `Recife-UBS-40-road` instance using `uv run python -m src.experiments.runner --phase 2 --tuned-config results/hpo_best_configs.json`, and verify `results/phase2_summary.csv`, `results/best_solutions.json`, and `results/recife_map.html` reflect the new certified `optimal_value` and 40 unique units.
- [x] 3.2 Run the full test suite (`uv run pytest`) and confirm all tests pass with zero regressions and `git status` shows only expected code, dataset, test, and result updates.
