# Design

## Context

See `proposal.md` for motivation and methodological rationale. Currently:
- `src/experiments/hpo.py` defaults to tuning on `[A-n32-k5, A-n60-k9]` (`DEFAULT_CVRPLIB_NAMES` lists all 4 CVRPLIB files including `A-n80-k10.vrp`) with defaults `--trials 30`, `--seeds 3`, `--generations 100`, `--hpo-seed 42`.
- `src/experiments/runner.py` loads all 4 CVRPLIB instances (`A-n32-k5`, `A-n45-k6`, `A-n60-k9`, `A-n80-k10`) plus `Recife-UBS-40-road`, defaults to legacy Phase 1 operator ablation (`run_phase1_ablation`, `select_best_operators`, `--phase1-seeds`) when neither `--tune` nor `--tuned-config` is passed, and uses different inline Phase 1 HPO defaults (`--hpo-trials 25`, `--hpo-generations None` falling back to `--generations=150`, tuning only on `A-n32-k5` and `A-n60-k9`).
- `src/experiments/progress.py` contains legacy Phase 1 ablation table builders (`build_phase1_summary_table`, `render_phase1_summary`).
- `results/` contains legacy Phase 1 ablation artifacts (`phase1_ablation.csv`, `phase1_summary.csv`, `phase1_histories.json`) and `A-n80-k10` plots/rows from previous runs.

## Goals / Non-Goals

**Goals:**
- Remove all legacy Phase 1 operator ablation code, CLI flags, progress helpers, tests, and stale result artifacts cleanly.
- Remove the unused `data/cvrplib/A-n80-k10.vrp` dataset file and its test/documentation references.
- Preserve the **Phase 1 → Phase 2** pipeline terminology while replacing Phase 1's methodology with Bayesian HPO (Optuna TPE): `runner.py` either loads pre-computed Phase 1 HPO configs via `--tuned-config` or executes Phase 1 HPO inline by default before Phase 2.
- Standardize the CVRPLIB training/benchmark suite to `A-n32-k5`, `A-n45-k6`, and `A-n60-k9`, with `Recife-UBS-40-road` as the sole held-out real-world evaluation scenario.
- Unify Phase 1 HPO default parameters (`trials=30`, `seeds=3`, `generations=100`, `hpo_seed=42`, training set `[A-n32-k5, A-n45-k6, A-n60-k9]`) across `hpo.py` and `runner.py`.
- Regenerate all artifacts in `results/` under the new protocol so the repository's committed outputs match the documented methodology.

**Non-Goals:**
- Modifying the core solver algorithms (`src/solver/`) or data loader implementations (`src/data/`).
- Changing the CSV column schemas of `phase2_results.csv`, `phase2_summary.csv`, `phase2_stats_tests.csv`, or the filenames/schemas of `hpo_best_configs.json`, `hpo_trials_*.csv`, and `best_solutions.json`.
- Tuning the deterministic, parameter-free Greedy baseline (`solve_greedy`).

## Decisions

### 1. Runner CLI mode: Phase 1 (Bayesian HPO) → Phase 2 with `--tuned-config` and optional `--tune` alias
- **Decision**: When `--tuned-config <path>` is passed, `runner.main()` validates and loads pre-computed Phase 1 `Pure_GA` and `Memetic_GA` configs and proceeds directly to Phase 2. When `--tuned-config` is omitted (whether or not `--tune` is passed), `runner.main()` executes Phase 1 inline via `run_hpo_suite(...)` on the 3 CVRPLIB training instances (`A-n32-k5`, `A-n45-k6`, `A-n60-k9`), saves Phase 1 HPO artifacts (`hpo_best_configs.json`, `hpo_trials_pure_ga.csv`, `hpo_trials_memetic_ga.csv`) to `--output-dir`, loads the resulting configs, and runs Phase 2. Keep `--tune` in a mutually exclusive group with `--tuned-config` so existing scripts passing `--tune` continue to work while passing both flags fails fast.
- **Alternatives considered**:
  - *Removing `--tune` entirely*: Slightly smaller CLI surface, but breaks existing user commands or scripts that explicitly pass `--tune` for clarity.
  - *Requiring `--tuned-config` with no inline Phase 1 HPO*: Forces two commands for every run and breaks single-command reproducibility via `uv run -m src.experiments.runner`.
- **Additional CLI cleanup**: Remove `--phase1-seeds` completely. Keep programmatic defaults (`crossover`, `mutation`, `pop_size`, `generations`, `local_search_rate`) on `run_phase2_comparison()` so unit tests calling it directly without `GAConfig` overrides remain ergonomic, while removing unused uniform-fallback CLI flags (`--pop-size`, `--ls-rate`) from `runner.build_arg_parser()` since `runner.main()` always supplies Phase 1 tuned `GAConfig` objects to Phase 2.

### 2. Shared 3-instance CVRPLIB training/benchmark suite (`A-n32-k5`, `A-n45-k6`, `A-n60-k9`)
- **Decision**:
  - Delete `data/cvrplib/A-n80-k10.vrp` and remove its parametrized entry from `tests/test_data_loading.py` since it is unused and not needed for backward compatibility.
  - Update `DEFAULT_CVRPLIB_NAMES` in `src/experiments/hpo.py` to `("A-n32-k5.vrp", "A-n45-k6.vrp", "A-n60-k9.vrp")` and have `_resolve_tuning_instances(None)` return all three. (Explicit `.vrp` file paths passed to `--instances` still work via the `Path(name).is_file()` branch.)
  - Update `load_cvrplib_suite()` in `src/experiments/runner.py` to load `["A-n32-k5.vrp", "A-n45-k6.vrp", "A-n60-k9.vrp"]`.
  - In `runner.main()`, Phase 1 HPO runs on `cvrplib_instances` (all 3 CVRPLIB instances) and Phase 2 runs on `cvrplib_instances + recife_instances` (the 3 CVRPLIB instances + `Recife-UBS-40-road`).
- **Alternatives considered**:
  - *Keeping `A-n80-k10` in Phase 2*: Rejected because it contradicts the decision report's protocol (`Recife-UBS-40-road` as the sole held-out evaluation scenario) and adds runtime overhead without serving the Recife-bracketing size range (32–60 nodes around Recife's 41 nodes).

### 3. Aligning runner Phase 1 HPO defaults with standalone HPO defaults
- **Decision**: Set `runner.py` defaults to `--hpo-trials 30`, `--hpo-seeds 3`, `--hpo-generations 100`, and `--hpo-seed 42`, matching `hpo.py` and the Methodology Decision Report. Keeping `--hpo-generations` fixed at `100` (independent of Phase 2's `--generations 150`) ensures consistent Phase 1 compute budgets regardless of how Phase 2's generation budget is configured.
- **Alternatives considered**:
  - *Keeping `--hpo-generations` defaulting to `--generations` (150)*: Causes standalone Phase 1 HPO (`100` gens) and inline runner Phase 1 HPO (`150` gens) to produce different tuned configs for the same seed.

### 4. Clean removal of legacy Phase 1 ablation code and stale artifacts
- **Decision**:
  - Delete `run_phase1_ablation` and `select_best_operators` from `src/experiments/runner.py`.
  - Delete `build_phase1_summary_table` and `render_phase1_summary` from `src/experiments/progress.py`, while preserving the existing HPO progress helpers and summary table title (`Hyperparameter Optimization Summary`) used by `src/experiments/hpo.py` and `tests/test_hpo.py`.
  - Use consistent **Phase 1 (Bayesian HPO) → Phase 2** phrasing across `runner.py` console output/docstrings, specs, and `README.md`.
  - Delete obsolete Phase 1 ablation tests from `tests/test_experiments.py` and replace them with tests covering default inline Phase 1 HPO → Phase 2 execution, 3-instance suite selection, and aligned defaults.
  - Delete stale `results/phase1_ablation.csv`, `results/phase1_summary.csv`, `results/phase1_histories.json`, `results/boxplot_A-n80-k10.png`, and `results/convergence_A-n80-k10.png` before running the fresh Phase 1 HPO + Phase 2 campaign so no outdated artifacts linger in `results/`.

## Risks / Trade-offs

- **Breaking change for callers importing removed Phase 1 ablation symbols or passing `--phase1-seeds` / `--pop-size` / `--ls-rate`** → Document clearly in `README.md` and `proposal.md`; update all internal references and tests in the same change.
- **Longer runtime for bare `uv run -m src.experiments.runner`** (now runs 30×2 Phase 1 HPO trials over 3 instances × 3 seeds before 30-seed Phase 2) → Users can run standalone Phase 1 HPO once and reuse `results/hpo_best_configs.json` via `--tuned-config`, or lower `--hpo-trials` / `--hpo-seeds` / `--phase2-seeds` for fast exploratory runs.
- **OSRM network availability during `recife_map.html` regeneration** → `generate_recife_map` already handles OSRM timeouts/errors gracefully with straight-line fallback, though street-snapped geometry is expected when online.
- **Symmetric-to-asymmetric domain shift** (Phase 1 HPO trains on symmetric Euclidean CVRPLIB instances while held-out evaluation runs on the asymmetric OSRM road network in Recife) → Explicitly document this in `README.md` as an intentional methodological feature testing out-of-distribution generalization with zero data leakage.

## Migration Plan

1. Delete unused `data/cvrplib/A-n80-k10.vrp` and remove its parametrized entry from `tests/test_data_loading.py`.
2. Apply code changes in `src/experiments/hpo.py`, `src/experiments/progress.py`, and `src/experiments/runner.py`.
3. Update `tests/test_hpo.py` and `tests/test_experiments.py` and verify the full `uv run pytest` suite passes.
4. Update `README.md` to reflect the Phase 1 (Bayesian HPO) → Phase 2 methodology, protocol table, CLI commands, and 3-instance CVRPLIB + Recife artifact inventory.
5. Remove stale `results/phase1_ablation.csv`, `results/phase1_summary.csv`, `results/phase1_histories.json`, `results/boxplot_A-n80-k10.png`, and `results/convergence_A-n80-k10.png`.
6. Run standalone Phase 1 HPO (`uv run -m src.experiments.hpo --instances A-n32-k5 A-n45-k6 A-n60-k9 --trials 30 --seeds 3 --generations 100`) followed by Phase 2 (`uv run -m src.experiments.runner --tuned-config results/hpo_best_configs.json`), and inspect the regenerated artifacts in `results/`.
