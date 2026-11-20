# Tasks

## 1. Phase 1 HPO Default Training Set, Unused Dataset Cleanup & Tests

- [x] 1.1 Update `DEFAULT_CVRPLIB_NAMES`, `_resolve_tuning_instances`, and `--instances` CLI help in `src/experiments/hpo.py` to default to `A-n32-k5`, `A-n45-k6`, and `A-n60-k9` (excluding `A-n80-k10` and holding out `Recife-UBS-40-road`), and add unit tests in `tests/test_hpo.py` verifying default training set resolution and CLI help; verify with `uv run pytest tests/test_hpo.py`.
- [x] 1.2 Delete unused `data/cvrplib/A-n80-k10.vrp` and remove the `A-n80-k10.vrp` parametrized case from `tests/test_data_loading.py`; verify only `A-n32-k5.vrp`, `A-n45-k6.vrp`, and `A-n60-k9.vrp` remain in `data/cvrplib/` and `uv run pytest tests/test_data_loading.py` passes.

## 2. Replace Phase 1 Ablation with Phase 1 Bayesian HPO in the Runner

- [x] 2.1 Remove legacy Phase 1 ablation summary table helpers (`build_phase1_summary_table`, `render_phase1_summary`) from `src/experiments/progress.py` and verify no ablation helper symbols remain in `src/experiments/progress.py`.
- [x] 2.2 Refactor `src/experiments/runner.py` to remove `run_phase1_ablation`, `select_best_operators`, and unused CLI flags (`--phase1-seeds`, `--pop-size`, `--ls-rate`); narrow `load_cvrplib_suite` to `A-n32-k5`, `A-n45-k6`, and `A-n60-k9`; align inline Phase 1 HPO defaults (`--hpo-trials 30`, `--hpo-seeds 3`, `--hpo-generations 100`, `--hpo-seed 42`); and make Phase 1 (inline Bayesian HPO) → Phase 2 the default workflow when `--tuned-config` is omitted (keeping `--tune` as an optional alias mutually exclusive with `--tuned-config`). Verify CLI options with `uv run -m src.experiments.runner --help`.
- [x] 2.3 Update `tests/test_experiments.py` to remove obsolete Phase 1 ablation/summary tests and add tests verifying 3-instance `load_cvrplib_suite()` (excluding `A-n80-k10`), aligned Phase 1 HPO CLI defaults, default inline Phase 1 HPO → Phase 2 execution when `--tuned-config` is omitted, `--tuned-config` execution without re-running Phase 1 HPO, and mutually exclusive/invalid flag rejection; verify with `uv run pytest`.

## 3. Documentation & Methodology Protocol

- [x] 3.1 Update `README.md` to present **Phase 1 (Bayesian HPO) → Phase 2 (Benchmarking & Statistical Evaluation)** as the primary experimental methodology (removing legacy Phase 1 operator ablation steps, `--phase1-seeds`, and `phase1_ablation.*` / `phase1_summary.csv` / `phase1_histories.json` artifacts), document the training/benchmark (`A-n32-k5`, `A-n45-k6`, `A-n60-k9`) vs. sole held-out real-world (`Recife-UBS-40-road`, asymmetric OSRM road network) split and domain shift, and document both 2-step (`hpo` + `runner --tuned-config`) and 1-step (`runner`) CLI commands; verify documented flags match `--help` and no references to operator ablation (`ablation`, `phase1_ablation`, `phase1_summary`, `--phase1-seeds`) or `A-n80-k10` remain anywhere in `README.md`.

## 4. Clean Stale Results & Regenerate Experimental Campaign

- [x] 4.1 Remove stale `results/phase1_ablation.csv`, `results/phase1_summary.csv`, `results/phase1_histories.json`, `results/boxplot_A-n80-k10.png`, and `results/convergence_A-n80-k10.png` and verify those files are deleted.
- [x] 4.2 Run standalone Phase 1 HPO (`uv run -m src.experiments.hpo --instances A-n32-k5 A-n45-k6 A-n60-k9 --trials 30 --seeds 3 --generations 100`) and verify `results/hpo_best_configs.json` records `instances == ["A-n32-k5", "A-n45-k6", "A-n60-k9"]`, `n_trials == 30`, `generations == 100`, `seeds == [1, 2, 3]`, and valid `Pure_GA` and `Memetic_GA` entries alongside 30-row `results/hpo_trials_pure_ga.csv` and `results/hpo_trials_memetic_ga.csv`.
- [x] 4.3 Run 30-seed Phase 2 benchmarking, statistical tests, plots, and Recife map generation (`uv run -m src.experiments.runner --tuned-config results/hpo_best_configs.json`) and verify `results/phase2_summary.csv`, `results/phase2_stats_tests.csv`, `results/best_solutions.json`, `results/convergence_*.png`, `results/boxplot_*.png`, and `results/recife_map.html` cover exactly `A-n32-k5`, `A-n45-k6`, `A-n60-k9`, and `Recife-UBS-40-road` with zero legacy `phase1_*` or `A-n80-k10` artifacts.
- [x] 4.4 Run the full test suite (`uv run pytest`) and linter (`uv run ruff check src tests`) to verify all checks pass cleanly after code, doc, and artifact updates.
