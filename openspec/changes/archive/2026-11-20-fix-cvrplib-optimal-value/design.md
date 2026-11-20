# Design

## Context

See [proposal.md](proposal.md) for motivation. Currently:
- `data/cvrplib/A-n60-k9.vrp` line 2 carries the legacy 1995 header `COMMENT : (Augerat et al, Min no of trucks: 9, Best value: 1408)` instead of the proven CVRPLIB optimum `1354`.
- `src/data/cvrplib_loader.py` uses `_OPT_VALUE_RE = re.compile(r"(?:Optimal|Best)\s+value\s*:\s*([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)`, which populates `CVRPInstance.optimal_value` from both `Optimal value` and `Best value`.
- Downstream consumers (`src/experiments/hpo.py`, `src/experiments/stats.py`, `src/experiments/plots.py`, `src/experiments/progress.py`, and `tests/test_solver.py`) treat `CVRPInstance.optimal_value` as a proven lower/optimal bound (e.g., computing `% gap`, plotting `Optimal (...)` reference lines, and asserting `res.distance >= inst.optimal_value`).

## Goals / Non-Goals

**Goals:**
- Ensure `data/cvrplib/A-n60-k9.vrp` records the proven CVRPLIB optimal value (`1354`) while preserving its coordinate, demand, capacity, and depot sections unchanged.
- Guarantee `load_cvrplib()` only populates `CVRPInstance.optimal_value` from explicit `Optimal value:` annotations, preventing unproven upper bounds (`Best value:`) from silently entering optimality-gap calculations.
- Keep all versioned tests, docs, and experimental artifacts (`results/`) consistent with `A-n60-k9` having `optimal_value = 1354.0`.

**Non-Goals:**
- Introducing a separate `best_known_value` field on `CVRPInstance` or changing the CSV/JSON schemas of `results/`.
- Modifying the coordinates, demands, capacity, or solver algorithms for any benchmark instance.

## Decisions

1. **Restrict `_OPT_VALUE_RE` to `Optimal value:` only (leave `Best value:` as `optimal_value = None`)**
   - *Rationale:* Every downstream consumer in the project interprets `optimal_value` as a proven global optimum (including `tests/test_solver.py` asserting `res.distance >= inst.optimal_value` and `plots.py` labeling the reference line `Optimal`). Loading an unproven upper bound into `optimal_value` can produce negative optimality gaps or factually wrong labels.
   - *Alternative considered:* Adding a separate `best_known_value: float | None` field to `CVRPInstance`. Rejected because all bundled benchmarks (`A-n32-k5`, `A-n45-k6`, `A-n60-k9`, and `Recife-UBS-40-road`) have proven optima, so an extra field would add schema complexity with no active consumer.

2. **Update `data/cvrplib/A-n60-k9.vrp` line 2 in place**
   - *Rationale:* Changing only `Best value: 1408` → `Optimal value: 1354` in the `COMMENT` line preserves the exact node coordinates, demands, capacity (`100`), truck count (`9`), and depot section while matching the proven CVRPLIB optimum published on the PUC-Rio portal.

3. **Re-run the full Phase 1 HPO → Phase 2 pipeline to refresh `results/`**
   - *Rationale:* `src/experiments/hpo.py` optimizes mean `% gap` across `A-n32-k5`, `A-n45-k6`, and `A-n60-k9`. Changing `A-n60-k9`'s `optimal_value` from `1408.0` to `1354.0` alters the exact HPO objective value and relative instance weighting (`1408/1354 ≈ 1.04`), as well as all `A-n60-k9` gap columns in `phase2_results.csv`/`phase2_summary.csv` and the `Optimal` line in `boxplot_A-n60-k9.png` and `convergence_A-n60-k9.png`. Re-running `uv run -m src.experiments.runner` guarantees end-to-end reproducibility and factual consistency across all versioned outputs.
   - *Alternative considered:* Only recalculating `phase2_summary.csv` and replotting `A-n60-k9`. Rejected because `hpo_trials_*.csv` and `hpo_best_configs.json` would remain derived from the erroneous `1408.0` value.

## Risks / Trade-offs

- **Re-running Phase 1 HPO may shift tuned hyperparameters slightly** → Acceptable and desirable because the previous HPO objective used an incorrect reference value for `A-n60-k9`; the pipeline is deterministic (`--hpo-seed 42`) and fast to re-run locally.
- **External `.vrp` files using only `Best value:` will now load with `optimal_value=None`** → Downstream stats, progress, and plotting code already handle `optimal_value=None` gracefully by omitting `% gap` and the optimal reference line; `hpo.py` explicitly raises a descriptive error if an HPO training instance lacks a proven `optimal_value`.
