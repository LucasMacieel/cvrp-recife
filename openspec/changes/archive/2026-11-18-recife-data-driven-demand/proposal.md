# Proposal

## Why

The Recife/PE geographic CVRP scenario currently assigns synthetic uniform random demands (`rng.integers(10, 31)`) to UBS and USF health units in `scripts/prepare_recife_data.py`, weakening the empirical validity of the real-world case study. Replacing these synthetic numbers with replenishment demand proxies derived from official Recife Open Data municipal pharmacy stockout records grounds the routing problem in real municipal supply shortages while preserving CVRP feasibility and offline experimental reproducibility.

## What Changes

- Cross-reference the base Recife UBS/USF health unit network in `scripts/prepare_recife_data.py` against the official Recife Open Data pharmacy inventory CSV (`medicamentos-por-unidade-de-saude.csv` from the `medicamentos` CKAN package).
- Link health units to pharmacy stock records using a tiered deterministic join strategy:
  1. Primary key: `US <number>` unit code extracted from `nome_oficial` and `unidade`.
  2. Fallback key: normalized unit name (accent-stripped, case-folded) combined with `bairro`.
  3. Unmatched fallback: median raw stockout count of matched units of the same unit type (`UBS` or `USF`), with a global matched median fallback if an entire unit type has zero matches.
- Compute each unit's raw replenishment demand proxy as its REMUME stockout count: `x_i = count(items at unit i with quantidade = 0)`.
- Scale customer stockout counts deterministically via min-max integer normalization into a configurable CVRP-feasible range `[d_min, d_max]` (default `[10, 40]` for `capacity = 100`), keeping `demand = 0` for `DEPOT-CAF` and guaranteeing `1 <= d_i <= capacity` for all customer nodes.
- Persist scaled `demand` values alongside provenance metadata (`raw_stockouts`, `total_items`, `demand_match_method`, and dataset-level demand estimation metadata) in `data/recife_ubs/recife_ubs.json`, regenerating the static dataset artifact without requiring network access during `src/data/recife_loader.py` loading or experimental runs.
- Add unit tests covering record linkage, stockout counting, min-max integer scaling, edge cases (degenerate constant stockouts, unmatched fallbacks), and offline loader compatibility with enriched metadata.

## Capabilities

### New Capabilities

(None)

### Modified Capabilities

- `cvrp-data-loading`: Add requirements for data-driven Recife/PE replenishment demand estimation via open-data pharmacy stockout cross-referencing, CVRP-feasible integer normalization, and persistence of scaled demands with raw stockout metadata into the static offline dataset.

## Impact

- **Affected scripts**: `scripts/prepare_recife_data.py` (data fetching, cross-referencing, stockout aggregation, min-max scaling, JSON serialization).
- **Affected static data**: `data/recife_ubs/recife_ubs.json` (updated customer `demand` values, per-node raw stockout metadata, and top-level demand provenance fields; node set, coordinates, and `distance_matrix_road.npy` remain unchanged).
- **Unchanged runtime modules**: `src/data/recife_loader.py`, `src/data/models.py`, solver modules, and `src/experiments/runner.py` remain completely offline and compatible with the regenerated JSON.
- **Affected tests**: `tests/test_data_loading.py` (or a dedicated test module for Recife demand estimation) to verify linkage, scaling, fallback behavior, and static dataset integrity.
- **Dependencies**: No new third-party dependencies required (uses existing `requests`, `numpy`, and Python standard library `csv`, `re`, `unicodedata`, `statistics`).
- **Downstream experiment artifacts**: Existing `results/` files were generated with synthetic demands; re-running `python -m src.experiments.runner` after regenerating `recife_ubs.json` will refresh experimental results on the empirical demands (optional/explicitly tracked in tasks if desired, without altering solver behavior).
