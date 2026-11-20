# Proposal

## Why

The repository currently reports the optimal value of CVRPLIB benchmark `A-n60-k9` as `1408`, which is a factual error: `1408` is an outdated 1995 upper bound (`Best value: 1408`) from a legacy header in `data/cvrplib/A-n60-k9.vrp`, whereas the proven optimal value in CVRPLIB (PUC-Rio portal, `http://vrp.galgos.inf.puc-rio.br/`) is `1354`. This error propagated into HPO objectives, Phase 2 optimality gap tables, and benchmark plots because `src/data/cvrplib_loader.py` conflates `"Best value"` (an unproven upper bound) with `"Optimal value"` (a proven optimum) when populating `CVRPInstance.optimal_value`.

## What Changes

- Update `data/cvrplib/A-n60-k9.vrp` line 2 `COMMENT` header from `Best value: 1408` to `Optimal value: 1354` so the versioned benchmark reflects the proven CVRPLIB optimum.
- Restrict `src/data/cvrplib_loader.py` (`_OPT_VALUE_RE`) to extract `optimal_value` exclusively from `Optimal value:` annotations in `COMMENT` headers, leaving `optimal_value` as `None` when a `.vrp` file only reports `Best value:` (an unproven upper bound).
- Update `CVRPInstance.optimal_value` documentation in `src/data/models.py` and `README.md` so `optimal_value` is documented strictly as a proven optimal total distance.
- Update `tests/test_data_loading.py` to assert `A-n60-k9` loads with `optimal_value == 1354.0` and add regression tests confirming `Best value:` headers are ignored (`optimal_value is None`) while `Optimal value:` headers are parsed.
- Regenerate versioned experimental outputs under `results/` (Phase 1 HPO trials/configs, Phase 2 CSVs, and `A-n60-k9` plots) so all reported optimality gaps and reference lines reflect the true optimum `1354.0`.

## Capabilities

### New Capabilities

### Modified Capabilities
- `cvrp-data-loading`: Tighten `Loading CVRPLIB instances` so `optimal_value` is parsed exclusively from proven `Optimal value` headers (never from `Best value` upper bounds) and `A-n60-k9` provides its proven CVRPLIB optimum (`1354`).

## Impact

- **Data**: `data/cvrplib/A-n60-k9.vrp` (`COMMENT` header updated from `Best value: 1408` to `Optimal value: 1354`).
- **Code**: `src/data/cvrplib_loader.py` (regex restricted to `Optimal value`), `src/data/models.py` (docstring alignment).
- **Tests**: `tests/test_data_loading.py` (updated expected optimum for `A-n60-k9` and new regression coverage for `Best value` vs `Optimal value`).
- **Docs**: `README.md` (input format description for CVRPLIB `COMMENT` parsing).
- **Experiment Artifacts**: `results/` (`hpo_best_configs.json`, `hpo_trials_*.csv`, `phase2_results.csv`, `phase2_summary.csv`, `phase2_stats_tests.csv`, `phase2_histories.json`, `best_solutions.json`, and `*.png` charts) regenerated against `optimal_value = 1354.0` for `A-n60-k9`.
