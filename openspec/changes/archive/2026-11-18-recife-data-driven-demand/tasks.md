# Tasks

## 1. Pharmacy Stock Ingestion & Record Linkage

- [x] 1.1 Add `MEDICAMENTOS_CSV_URL` and pure stock-parsing helpers (`parse_stock_records`, `extract_us_code`, `normalize_text`) in `scripts/prepare_recife_data.py` supporting `;`-delimited UTF-8-SIG CSVs, comma-decimal `quantidade` parsing (`"0,0"`, `"0.0"`, `"0"`), latest `data_carga` snapshot filtering per unit, and optional local CSV loading; verify with unit tests in `tests/test_recife_demand.py` covering comma-decimal zero counts, multi-date snapshot filtering, and `US 128` vs. `US 128.1` code extraction.
- [x] 1.2 Implement tiered deterministic linkage (`link_nodes_to_stock`) in `scripts/prepare_recife_data.py` matching customer nodes by (1) `US <number>` code with multi-entry disambiguation by normalized `bairro`/name overlap, (2) fallback normalized `(name, bairro)`, and (3) type-stratified median imputation (`UBS` / `USF`, falling back to global matched median or raising `ValueError` when zero units match); verify with unit tests in `tests/test_recife_demand.py` covering all three tiers, disambiguation, and zero-match error handling.

## 2. CVRP-Feasible Normalization & Metadata Persistence

- [x] 2.1 Implement `scale_demands_minmax` and `assign_empirical_demands` in `scripts/prepare_recife_data.py` validating `1 <= d_min <= d_max <= capacity`, computing rounded min-max integer demands (with constant-stockout zero-spread handling), keeping `demand = 0` for `DEPOT-CAF`, and populating per-node (`raw_stockouts`, `total_items`, `demand_match_method`, optional `imputed_stockouts`) and top-level `demand_metadata` fields; verify with unit tests in `tests/test_recife_demand.py` covering varying counts, degenerate equal counts, invalid bounds rejection, and depot preservation.
- [x] 2.2 Remove synthetic `rng.integers(10, 31)` demand generation from `_collect_recife_nodes` in `scripts/prepare_recife_data.py`, wire `main()` and `argparse` CLI flags (`--output-dir`, `--d-min`, `--d-max`, `--capacity`, `--stock-csv`) to run empirical demand estimation and persist the updated `recife_ubs.json` format, and update `README.md` section 2 to document the pharmacy stockout demand source; verify `python scripts/prepare_recife_data.py --help` exits 0 and `load_recife` unit test in `tests/test_data_loading.py` loads enriched JSON metadata offline without error.

## 3. Dataset Regeneration & End-to-End Verification

- [x] 3.1 Run `python scripts/prepare_recife_data.py` to regenerate `data/recife_ubs/recife_ubs.json` from live Recife Open Data and verify the persisted file has 41 nodes (matching existing node IDs and coordinates), `demand == 0` at index 0, `10 <= demand <= 40` across all 40 customer nodes, populated `raw_stockouts`/`total_items`/`demand_match_method`/`demand_metadata`, and valid `distance_matrix_road.npy`.
- [x] 3.2 Run the full `pytest` suite (`pytest`) and an offline `load_recife("data/recife_ubs", mode="road")` + `load_recife("data/recife_ubs", mode="haversine")` integrity check verifying all unit tests, solver smoke tests, and offline CVRP instance validations pass with zero network calls.
