# Proposal

## Why

The experimental pipeline currently uses a legacy fixed-parameter Phase 1 2×2 operator ablation (`OX`/`PMX` × `Swap`/`Inversion` on `Pure_GA` only) alongside an optional Bayesian HPO path, tunes by default on only two CVRPLIB instances (`A-n32-k5`, `A-n60-k9`), and evaluates four CVRPLIB instances including `A-n80-k10` in Phase 2. Because Optuna TPE (`src/experiments/hpo.py`) already jointly optimizes categorical operators and all numeric hyperparameters independently for both `Pure_GA` and `Memetic_GA`, keeping Phase 1 operator ablation is redundant and risks unfair comparisons driven by `Pure_GA`-only operator selection. Replacing Phase 1's methodology with Bayesian HPO trained on `A-n32-k5`, `A-n45-k6`, and `A-n60-k9` — while keeping the Phase 1 → Phase 2 pipeline structure and using `Recife-UBS-40-road` as the sole held-out real-world evaluation scenario — makes the experimental protocol cleaner, fairer, and leakage-free.

## What Changes

- **BREAKING** Remove legacy Phase 1 operator ablation code and CLI options completely from the experiment runner and progress reporting (`run_phase1_ablation`, `select_best_operators`, `build_phase1_summary_table`, `render_phase1_summary`, `--phase1-seeds`, and the ablation branch in `src/experiments/runner.py`).
- **BREAKING** Replace Phase 1's methodology with Bayesian HPO (Optuna TPE) in the primary Phase 1 → Phase 2 runner workflow: invoking `src/experiments/runner.py` without `--tuned-config` executes Phase 1 Bayesian HPO inline on the CVRPLIB training set before Phase 2, while `--tuned-config <path>` loads pre-computed Phase 1 HPO configs (`Pure_GA` and `Memetic_GA`) directly into Phase 2.
- **BREAKING** Remove `A-n80-k10` completely — delete `data/cvrplib/A-n80-k10.vrp`, remove it from `load_cvrplib_suite`, default Phase 1 HPO instance resolution, `tests/test_data_loading.py`, and `README.md` — scoping the benchmark/training set to `A-n32-k5`, `A-n45-k6`, and `A-n60-k9` so that `Recife-UBS-40-road` (41 nodes, asymmetric OSRM road network) serves as the sole held-out real-world evaluation instance.
- Align Phase 1 HPO defaults across `src/experiments/hpo.py` and `src/experiments/runner.py`: default training instances `A-n32-k5`, `A-n45-k6`, `A-n60-k9`, `--hpo-trials` = `30`, `--hpo-seeds` = `3`, `--hpo-generations` = `100`, and `--hpo-seed` = `42`.
- Update `README.md`, unit/CLI tests (`tests/test_experiments.py`, `tests/test_hpo.py`, `tests/test_data_loading.py`), and regenerate `results/` (removing stale Phase 1 ablation files `phase1_*` and `A-n80-k10` plots, and re-running Phase 1 HPO + 30-seed Phase 2 + plots + Recife map).

## Capabilities

### New Capabilities
<!-- No new capabilities; this change refines existing experimental benchmarking and HPO specifications. -->

### Modified Capabilities
- `experiment-benchmarking`: Remove legacy Phase 1 operator ablation execution, CLI/progress reporting, and fallback requirements; replace Phase 1 with Bayesian HPO in the primary Phase 1 → Phase 2 workflow; narrow the default CVRPLIB benchmark suite to `A-n32-k5`, `A-n45-k6`, and `A-n60-k9` with `Recife-UBS-40-road` as the sole held-out real-world evaluation instance.
- `hyperparameter-optimization`: Update the default Phase 1 HPO training instance set to `A-n32-k5`, `A-n45-k6`, and `A-n60-k9` (excluding `A-n80-k10` and strictly holding out `Recife-UBS-40-road` from default tuning) and align default HPO budget parameters across standalone and runner invocations.

## Impact

- **Code**: `src/experiments/runner.py`, `src/experiments/hpo.py`, `src/experiments/progress.py`.
- **Data**: Delete unused `data/cvrplib/A-n80-k10.vrp`.
- **Tests**: `tests/test_experiments.py`, `tests/test_hpo.py`, `tests/test_data_loading.py`.
- **Documentation**: `README.md` (Phase 1 Bayesian HPO → Phase 2 methodology, experimental protocol, train/test split, CLI usage, and output artifact list).
- **Artifacts**: `results/` refreshed via standalone Phase 1 HPO (30 trials, 3 seeds, 100 generations on `A-n32-k5`, `A-n45-k6`, `A-n60-k9`) followed by 30-seed Phase 2 benchmarking and post-processing; stale `results/phase1_ablation.csv`, `results/phase1_summary.csv`, `results/phase1_histories.json`, `results/boxplot_A-n80-k10.png`, and `results/convergence_A-n80-k10.png` removed.
