# Design

## Context

See `proposal.md` for motivation and `specs/cvrp-data-loading/spec.md` for behavioral requirements.

Currently, `scripts/prepare_recife_data.py` fetches `unidades-basicas-de-saude-ubs.csv` and `unidades-de-saude-da-familia-usf.csv` from `dados.recife.pe.gov.br`, selects 40 customer nodes (anchored by `DEPOT-CAF` at index `0`), assigns synthetic demands via `rng.integers(10, 31)`, queries OSRM (with Haversine fallback) for the `41 x 41` road distance matrix, and persists `data/recife_ubs/recife_ubs.json` and `data/recife_ubs/distance_matrix_road.npy`.

At runtime, `src/data/recife_loader.py` reads only `name`, `capacity`, `depot`, and each node's `lat`, `lon`, `demand`, and `name` fields from `recife_ubs.json`, passing them to `CVRPInstance` (`src/data/models.py`), which enforces `int64` demands, `demands[depot] == 0`, and `0 <= demands[i] <= capacity` (`capacity = 100`). Extra fields in `recife_ubs.json` are safely ignored by the offline loader.

Inspection of the Recife Open Data `medicamentos` CKAN package (`medicamentos-por-unidade-de-saude.csv`, ~6.8 MB, 40,393 lines) revealed key data characteristics that shape this design:
- Semicolon-delimited (`;`), UTF-8 CSV with columns `distrito`, `bairro`, `unidade`, `classe`, `apresentacao`, `tipo_produto`, `codigo_produto`, `produto`, `cadum`, `data_carga`, `quantidade`.
- `quantidade` uses Portuguese comma decimals (e.g., `"0,0"`, `"76,0"`).
- `tipo_produto` contains two medication categories (`MEDICAMENTOS` and `MEDICAMENTOS P/ PACIENTES ESPECIAIS`).
- `data_carga` is currently a single snapshot (`"2024-10-10"`).
- A few `US` codes include decimal sub-unit suffixes (e.g., `US 128.1`) or appear under multiple facility entries (e.g., a Policlínica and a Farmácia da Família sharing a code).
- Across the 40 current customer nodes in `recife_ubs.json`, 35 match directly via `US <number>` (raw stockout counts ranging from 82 to 212), while 5 units (1 UBS and 4 USFs) are absent from the stock dataset. Three pairs of selected nodes are co-located UBS/USF facilities sharing a `US` code (`US 121`, `US 137`, `US 155`).

## Goals / Non-Goals

**Goals:**
- Replace random demand generation in `scripts/prepare_recife_data.py` with deterministic, empirically grounded replenishment demand estimation from `medicamentos-por-unidade-de-saude.csv`.
- Factor parsing, linkage, imputation, and min-max scaling into pure, importable helper functions in `scripts/prepare_recife_data.py` so the full logic is unit-testable offline without HTTP calls.
- Preserve exact backward compatibility with `src/data/recife_loader.py`, `src/data/models.py`, and existing node selection/ordering.
- Persist full demand provenance (raw stockouts, total items, match method, dataset-level scaling metadata) in `data/recife_ubs/recife_ubs.json`.

**Non-Goals:**
- Modifying `src/data/recife_loader.py`, `src/data/models.py`, solver algorithms, or `src/experiments/runner.py`.
- Changing which 40 UBS/USF nodes are selected or altering the OSRM/Haversine distance matrix logic.
- Fetching open data at experiment runtime (all network access stays confined to `scripts/prepare_recife_data.py`).
- Fuzzy/edit-distance matching across conflicting `US <number>` codes (risks mislinking distinct facilities).

## Decisions

### 1. Pharmacy Stock Source URL, Parsing, and Snapshot Handling
- **Decision**: Add `MEDICAMENTOS_CSV_URL` pointing to the official Recife Open Data CKAN CSV resource (`https://dados.recife.pe.gov.br/dataset/8ae2b6b5-51b5-403a-9dea-973a8ed1aca4/resource/1b8142f9-d801-4b54-88ca-5a1df3bd6884/download/medicamentos-por-unidade-de-saude.csv`), with an optional `--stock-csv <path>` CLI argument / `stock_csv_path` parameter to ingest a local CSV file when desired.
- **Parsing**: Decode with `utf-8-sig` and parse with `csv.DictReader(..., delimiter=";")`. Parse `quantidade` via `_parse_float` (replacing `,` with `.`) and count a row as a stockout when `qty == 0.0` (ignoring rows with unparseable `quantidade`). Include all medication rows in the CSV (`MEDICAMENTOS` and `MEDICAMENTOS P/ PACIENTES ESPECIAIS`).
- **Snapshot guard**: Track `data_carga` per stock unit; if multiple `data_carga` dates ever appear for the same `(unidade, bairro)` entry in a future portal update, retain only rows from that entry's latest `data_carga` (lexicographical ISO `YYYY-MM-DD` max) before counting `raw_stockouts` and `total_items`.
- **Rationale**: Matches the existing hardcoded-URL pattern used for `UBS_CSV_URL` and `USF_CSV_URL`, avoids extra CKAN API calls, correctly handles Portuguese decimal formatting (`"0,0"`), and prevents double-counting if the portal ever appends multi-date history.
- **Alternative considered**: Querying the CKAN `package_show` API dynamically on every run. Rejected to keep network calls minimal and consistent with existing resource URL constants.

### 2. Tiered Deterministic Record Linkage and Disambiguation
- **Decision**: Aggregate stock records per unique `(unidade, bairro)` into `StockSummary(unidade, bairro, raw_stockouts, total_items, data_carga)`, then link each customer node in three tiers:
  1. **Primary key (`us_code`)**: Extract the `US` code using case-insensitive regex `\bUS\s*0*(\d+(?:\.\d+)?)\b` from both `node["name"]` (`nome_oficial`) and stock `unidade`. Retaining optional `(?:\.\d+)?` prevents sub-units like `US 128.1` from colliding with `US 128`.
     - If a `US` code maps to multiple stock entries, disambiguate deterministically by: (a) matching normalized `bairro`, (b) highest token overlap between normalized unit names, and (c) lexicographical order on `unidade`.
  2. **Fallback key (`name_bairro`)**: Normalize strings via NFKD Unicode decomposition (stripping combining accents), lowercasing, removing non-alphanumeric characters, collapsing whitespace, and stripping leading facility-type tokens (`us <num>`, `ubs`, `usf`, `psf`, `cs`) to build a `(normalized_name, normalized_bairro)` lookup index.
  3. **Unmatched fallback (`type_median_fallback` / `global_median_fallback`)**: For units unmatched by Tiers 1 and 2, compute the raw proxy `x_i` as `float(statistics.median(matched_raw_stockouts_for_type))` using all matched customer nodes of the same `type` (`UBS` or `USF`). If no nodes of that type matched, fall back to the median across all matched customer nodes (`global_median_fallback`). If zero customer nodes matched overall, raise a `ValueError` to fail fast instead of emitting invalid data.
- **Rationale**: Directly captures 35/40 units via authoritative municipal `US` codes, handles name/formatting differences safely via normalized `(name, bairro)`, and uses type-stratified median imputation for the 5 units absent from the pharmacy dataset without distorting the matched `[min(x), max(x)]` range.
- **Alternative considered**: Fuzzy string matching (e.g., `difflib`) on unmatched units. Rejected because it can falsely pair distinct units in the same neighborhood (e.g., `us 138 psf dr luiz wilson` vs `US 276 FARMACIA DA FAMILIA DR. LUIZ WILSOM` in Bomba do Hemetério).

### 3. Min-Max Integer Scaling into CVRP-Feasible Range
- **Decision**: Scale customer raw proxies `x_i` (for all `M` customer nodes, excluding depot index `0`) into `[d_min, d_max]` (default `d_min = 10`, `d_max = 40` for `capacity = 100`):
  - Validate `1 <= d_min <= d_max <= capacity`; raise `ValueError` if invalid.
  - When `max(x) > min(x)`:
    ```python
    scaled = d_min + ((x_i - min_x) / (max_x - min_x)) * (d_max - d_min)
    d_i = max(d_min, min(d_max, int(round(scaled))))
    ```
  - When `max(x) == min(x)`: assign `d_i = int(round((d_min + d_max) / 2))` to every customer node.
  - Always set `demand = 0` on `DEPOT-CAF`.
- **Rationale**: Preserves relative replenishment urgency across health units while guaranteeing `CVRPInstance` feasibility (`int64`, `1 <= d_i <= Q`, `demands[0] == 0`) and keeping per-vehicle route sizes realistic (~2–10 units per truck at `Q = 100`).
- **Alternative considered**: Proportional scaling `round(Q * x_i / max(x))` or linear scaling without a lower bound (`[1, 40]`). Rejected because unbounded lower values under-weight lower-stockout units (which still have ~82 depleted items), whereas `[10, 40]` reflects substantial baseline replenishment volume across all units.

### 4. Persisted JSON Schema and Provenance Metadata
- **Decision**: Keep all existing fields in `data/recife_ubs/recife_ubs.json` intact (`name`, `capacity`, `depot`, `distance_unit`, `source`, `nodes[]` with `id`, `name`, `type`, `rpa`, `bairro`, `lat`, `lon`, `demand`) and add additive provenance metadata:
  - Per customer node:
    - `raw_stockouts`: `int | None` (`int` for matched units, `None` for fallback-imputed units)
    - `total_items`: `int | None` (`int` for matched units, `None` for fallback-imputed units)
    - `demand_match_method`: `"us_code" | "name_bairro" | "type_median_fallback" | "global_median_fallback"`
    - `imputed_stockouts`: `float` (included only on fallback-imputed nodes so observed vs. imputed values remain unambiguous)
  - Top-level `demand_metadata`:
    - `method`: `"stockout_count_minmax"`
    - `source_url`: `MEDICAMENTOS_CSV_URL`
    - `data_carga`: sorted unique snapshot date(s) used (e.g., `"2024-10-10"`)
    - `d_min`, `d_max`, `raw_min`, `raw_max`
    - `match_summary`: counts by match method (`us_code`, `name_bairro`, `type_median_fallback`, `global_median_fallback`)
  - Update top-level `source` string to include `medicamentos-por-unidade-de-saude.csv`.
  - Remove the synthetic `seed` / `rng.integers(10, 31)` logic from `_collect_recife_nodes`.
- **Rationale**: Gives full auditability for academic reporting and debugging while keeping `src/data/recife_loader.py` completely untouched and offline.

### 5. CLI Interface for `scripts/prepare_recife_data.py`
- **Decision**: Support `argparse` options in `scripts/prepare_recife_data.py` with backward-compatible defaults (`--output-dir data/recife_ubs`, `--d-min 10`, `--d-max 40`, `--capacity 100`, `--stock-csv <optional local file>`), while keeping `main(output_dir=...)` callable directly from Python with sensible defaults.
- **Rationale**: Zero-argument `python scripts/prepare_recife_data.py` continues to work identically to the README, while parameterized invocation supports reproducible offline regeneration and sensitivity analysis on `[d_min, d_max]`.

## Risks / Trade-offs

- **[External portal schema or URL change]** -> `dados.recife.pe.gov.br` could rename or relocate the CSV resource in the future. *Mitigation*: Persist the regenerated `data/recife_ubs/recife_ubs.json` in the repository so experiments and `pytest` stay 100% offline; provide `--stock-csv` for local snapshot ingestion; fail loudly with a clear error if required CSV columns are missing or zero units match.
- **[Shared `US` code across co-located UBS and USF nodes]** -> Three selected node pairs (`US 121`, `US 137`, `US 155`) share a `US` code in the municipal catalog and therefore receive identical raw stockout counts and scaled demands. *Mitigation*: Document this behavior clearly; it reflects the underlying municipal pharmacy reporting unit rather than a join error.
- **[Unmatched units rely on median imputation]** -> 5 of 40 units (1 UBS, 4 USFs) have no rows in `medicamentos-por-unidade-de-saude.csv`. *Mitigation*: Stratify fallback by unit type (`UBS` vs. `USF`) and record `demand_match_method` and `raw_stockouts: null` on each node so downstream analysis can distinguish observed from imputed units.
- **[Previously generated `results/` reflect synthetic demands]** -> Updating `data/recife_ubs/recife_ubs.json` alters customer demands for Recife instances, making existing files in `results/` stale relative to the new dataset. *Mitigation*: Keep dataset preparation and experiment re-execution cleanly separated; note in tasks/verification that `recife_ubs.json` is regenerated and validated offline via `load_recife` and `pytest`.

## Migration Plan

1. Implement stock CSV fetching/parsing, tiered linkage, imputation, and min-max scaling helpers in `scripts/prepare_recife_data.py`.
2. Add comprehensive offline unit tests (with synthetic fixture CSV rows) verifying primary linkage, fallback linkage, disambiguation, decimal `"0,0"` parsing, type-median imputation, min-max scaling, degenerate constant-demand handling, invalid-bound rejection, and `load_recife` offline compatibility.
3. Run `python scripts/prepare_recife_data.py` to regenerate `data/recife_ubs/recife_ubs.json` (and preserve valid `distance_matrix_road.npy`).
4. Verify via `pytest` and inspect `data/recife_ubs/recife_ubs.json` to confirm 41 nodes, `demand == 0` at depot, `10 <= demand <= 40` across all 40 customer nodes, and expected match counts (~35 `us_code`, ~5 `type_median_fallback`).
5. Rollback (if ever required): revert `scripts/prepare_recife_data.py` and `data/recife_ubs/` via `git checkout`.
