# Proposal

## Why

The static `Recife-UBS-40` dataset currently contains only 37 unique physical health units instead of 40 because cross-dataset deduplication between the Recife Open Data UBS and USF CSVs in `scripts/prepare_recife_data.py` relies solely on `(round(lat, 5), round(lon, 5))` (~1.1 m grid). Three facilities (`US 155`, `US 121`, and `US 137`) appear in both CSVs with 18–31 m coordinate offsets and placeholder CNES `9999999`, producing three duplicate customer nodes with colliding `USF-9999999` IDs, inflating total demand by +55 units (+8.5%, from 645 to 700, pushing $k_{LB} = \lceil 700/100 \rceil = 7$ to an exact multiple of $Q = 100$ and forcing $k^* = 8$), and injecting an artificial 596.1 m road loop between nodes 21 and 28 in Route 6 of the certified exact solution.

## What Changes

- Replace coordinate-grid-only deduplication in `scripts/prepare_recife_data.py` (`_collect_recife_nodes`) with multi-key cross-dataset deduplication across the UBS and USF CSVs, prioritizing UBS entries and rejecting duplicate physical units that match an already-selected unit by:
  - canonical `US <number>` unit code (`extract_us_code`),
  - valid (non-empty, non-placeholder) CNES code,
  - normalized `(name, bairro)` key (with unit-type prefixes stripped), or
  - rounded coordinate grid `(round(lat, 5), round(lon, 5))`.
- Guarantee unique, deterministic customer node `id`s when CNES is missing or a placeholder (such as `9999999` or `0000000`), and enforce post-collection integrity checks (unique node IDs, unique canonical `US` codes, and exact target customer count) before writing `recife_ubs.json`.
- Extend `src/data/recife_loader.py` (`load_recife`) to validate that loaded node `id`s are unique when present, preventing duplicate-ID datasets from silently entering offline experiments.
- Regenerate `data/recife_ubs/recife_ubs.json` and `data/recife_ubs/distance_matrix_road.npy` so `Recife-UBS-40` contains 40 genuinely distinct physical health units (plus `DEPOT-CAF`, 41 nodes total) with updated OSRM driving distances and empirical stockout demands.
- Re-certify the global optimum on the regenerated `Recife-UBS-40-road` instance using `scripts/solve_recife_exact.py` and persist the updated `optimal_value` and `exact_solution` certificate into `data/recife_ubs/recife_ubs.json`.
- Refresh downstream Phase 2 benchmark results and plots in `results/` for `Recife-UBS-40-road` using the existing CVRPLIB-tuned `results/hpo_best_configs.json` so reported gaps, routes, and maps reflect the deduplicated 40-unit network.
- Add unit tests for cross-dataset deduplication, placeholder CNES handling, node ID uniqueness, and dataset integrity assertions, and update the certified optimum assertion in `tests/test_data_loading.py`.

## Capabilities

### New Capabilities

(None)

### Modified Capabilities

- `cvrp-data-loading`: Add cross-dataset physical health unit deduplication and node ID uniqueness requirements for Recife/PE dataset preparation and offline loading, ensuring `Recife-UBS-40` contains 40 distinct physical facilities with unique identifiers.

## Impact

- **Affected scripts**: `scripts/prepare_recife_data.py` (node collection, multi-key deduplication, placeholder CNES handling, deterministic ID assignment, pre-write integrity validation).
- **Affected core loader**: `src/data/recife_loader.py` (duplicate node `id` validation in `load_recife`).
- **Affected static dataset**: `data/recife_ubs/recife_ubs.json` and `data/recife_ubs/distance_matrix_road.npy` (3 duplicate USF nodes replaced by 3 distinct USFs from the round-robin RPA pool; updated demands, OSRM road distances, and newly certified `optimal_value` / `exact_solution`).
- **Affected tests**: `tests/test_recife_demand.py` (new unit tests for `_collect_recife_nodes` deduplication and ID uniqueness) and `tests/test_data_loading.py` (duplicate-ID loader rejection test, dataset uniqueness assertions, updated certified `optimal_value`).
- **Affected experiment outputs**: `results/` Phase 2 tables, `best_solutions.json`, convergence/boxplot/route plots, and `recife_map.html` / `recife_map_preview.png` refreshed against the deduplicated `Recife-UBS-40-road` instance (HPO configs in `results/hpo_best_configs.json` are tuned on CVRPLIB and do not require re-tuning).
- **Dependencies**: None added or modified.
