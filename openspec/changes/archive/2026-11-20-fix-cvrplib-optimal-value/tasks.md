# Tasks

## 1. CVRPLIB Data & Loader Fix

- [x] 1.1 Update line 2 of `data/cvrplib/A-n60-k9.vrp` from `Best value: 1408` to `Optimal value: 1354` (leaving all coordinates, demands, capacity, and depot entries unchanged), and verify `git diff data/cvrplib/A-n60-k9.vrp` shows only the `COMMENT` line changed.
- [x] 1.2 Restrict `_OPT_VALUE_RE` in `src/data/cvrplib_loader.py` to match `Optimal value:` only (removing `Best` from the alternation) and update the `optimal_value` docstring in `src/data/models.py` and the CVRPLIB loader note in `README.md` to specify proven `Optimal value` headers only; verify via `uv run pytest tests/test_data_loading.py` after updating tests in 1.3.
- [x] 1.3 Update `tests/test_data_loading.py` so `A-n60-k9.vrp` expects `optimal_value == 1354.0` and add unit tests verifying `COMMENT` headers with `Best value: 1408` yield `optimal_value is None` while `Optimal value: 1354` yields `1354.0`; verify `uv run pytest tests/test_data_loading.py` passes.

## 2. Experiment Artifacts & Integration Verification

- [x] 2.1 Re-run the full Phase 1 HPO -> Phase 2 pipeline (`uv run -m src.experiments.runner`) to regenerate `results/` (HPO configs/trials, `phase2_results.csv`, `phase2_summary.csv`, `phase2_stats_tests.csv`, `phase2_histories.json`, `best_solutions.json`, and plots), and verify `results/phase2_summary.csv` and `results/phase2_results.csv` report `optimal_value == 1354.0` (with no `1408` entries) for `A-n60-k9`.
- [x] 2.2 Run the full test suite (`uv run pytest`) and confirm all tests pass with zero failures.
