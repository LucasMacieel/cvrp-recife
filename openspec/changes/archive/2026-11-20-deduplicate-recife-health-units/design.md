# Design

## Context

See `proposal.md` for motivation and observed impact of the three duplicate physical health units (`US 155`, `US 121`, `US 137`) in `data/recife_ubs/recife_ubs.json`.

Currently, `scripts/prepare_recife_data.py` (`_collect_recife_nodes`) ingests UBS rows first, then fills remaining slots up to `target_customers=40` via round-robin sampling across RPAs from the USF CSV. Deduplication is performed solely via `seen_coords` keyed on `(round(lat, 5), round(lon, 5))` (~1.1 m grid), and node IDs are formatted directly as `f"{unit_type}-{cnes}"` without checking for placeholder CNES values (e.g., `9999999`) or ID collisions. `src/data/recife_loader.py` (`load_recife`) does not currently check node `id` uniqueness.

## Goals / Non-Goals

**Goals:**
- Prevent physical health units appearing in both the UBS and USF municipal CSVs (or repeated within either CSV) from being selected more than once, even when coordinates are shifted by 15–50 m or CNES is a placeholder.
- Avoid false positives when distinct facilities happen to sit near each other (e.g., `US 112` and `US 225` in Iputinga are ~45.5 m apart with distinct CNES, US codes, and names).
- Guarantee every node in `recife_ubs.json` has a unique, deterministic `id`, and fail fast in both dataset preparation and `load_recife` if duplicate IDs are encountered.
- Regenerate `data/recife_ubs/recife_ubs.json` and `data/recife_ubs/distance_matrix_road.npy`, re-certify the exact optimum via `scripts/solve_recife_exact.py`, and refresh Phase 2 benchmark results and plots.

**Non-Goals:**
- Changing the CVRP model, vehicle capacity (`Q = 100`), demand scaling bounds (`[10, 40]`), or pharmacy stockout linkage rules.
- Re-running Phase 1 HPO (`results/hpo_best_configs.json`), which tunes GA hyperparameters on CVRPLIB instances rather than `Recife-UBS-40-road`.
- Introducing external geospatial clustering dependencies or modifying solver algorithms.

## Decisions

### 1. Multi-key identity deduplication (no broad geodesic radius filter)
In `_collect_recife_nodes`, track four identity sets across all selected customer nodes:
1. `seen_us_codes`: canonical `US <number>` extracted via existing `extract_us_code(name)` (handles case, leading zeros, and decimal sub-units like `US 128.1`).
2. `seen_cnes`: normalized valid CNES codes (digits/stripped string, excluding empty strings and placeholder sentinels where all characters are `"0"` or `"9"`, e.g., `"0000000"`, `"9999999"`).
3. `seen_name_bairro`: `(normalize_text(name, strip_prefix_tokens=True), normalize_text(bairro))` when `name` is non-empty.
4. `seen_coords`: `(round(lat, 5), round(lon, 5))` exact/sub-meter coordinate duplicate guard.

**Rationale:** All three known duplicates (`US 155`, `US 121`, `US 137`) are caught immediately by `seen_us_codes` (and `US 121` / `US 155` also match `seen_name_bairro`). Checking `seen_cnes` catches cross-listed units whose official names diverge or omit a US code.
**Alternative considered:** A geodesic proximity threshold (e.g., 50 m Haversine radius). Rejected because legitimate distinct facilities in dense urban Recife neighborhoods (such as `US 112` / `UBS-0001813` and `US 225` / `USF-0022306` in Iputinga, ~45.5 m apart) would be falsely collapsed.

### 2. Refactor `_collect_recife_nodes` to accept injected rows for deterministic unit testing
Extract a pure helper (e.g., `select_recife_nodes(ubs_rows, usf_rows, target_customers=40)`) called by `_collect_recife_nodes(target_customers=40)`.

**Rationale:** `_collect_recife_nodes` currently fetches live CSVs directly via `_fetch_csv_rows`, making it awkward to unit test without monkeypatching network calls. Separating row selection/deduplication into a pure function makes unit tests fast, offline, and deterministic.

### 3. Deterministic unique node IDs for missing or placeholder CNES
Define `_is_placeholder_cnes(cnes: str) -> bool` returning `True` when `cnes` is empty or consists solely of `"0"` or `"9"` (such as `"9999999"` or `"0000000"`).
- When CNES is valid: `base_id = f"{unit_type}-{cnes}"`.
- When CNES is missing or placeholder: prefer canonical US code (`f"{unit_type}-US{us_code.split()[1]}"` if `us_code` is present), otherwise `f"{unit_type}-{len(selected) + 1:04d}"`.
- Maintain `seen_ids` and if a collision still occurs, disambiguate deterministically with a numeric suffix (`-2`, `-3`, ...), and validate post-selection that `len(node_ids) == len(set(node_ids))` and `len(us_codes) == len(set(us_codes))`.

**Rationale:** Prevents placeholder CNES entries in legitimate non-duplicate USF rows from colliding on `USF-9999999` while keeping existing valid `UBS-<cnes>` / `USF-<cnes>` IDs completely unchanged.

### 4. Loader-level duplicate ID guard
In `src/data/recife_loader.py` (`load_recife`), extract node IDs when `"id"` is present and raise `ValueError` with the offending duplicate ID(s) if any ID repeats.

**Rationale:** Defense in depth — ensures offline experiments and tests fail fast if a stale or corrupted `recife_ubs.json` contains duplicate node IDs, without breaking backward compatibility for minimal fixtures that omit `"id"` (though all existing fixtures provide unique `"id"`s).

### 5. Dataset regeneration, exact re-certification, and Phase 2 refresh order
1. Run `uv run python scripts/prepare_recife_data.py` to regenerate `data/recife_ubs/recife_ubs.json` and `data/recife_ubs/distance_matrix_road.npy` (which clears stale `optimal_value` / `exact_solution`).
2. Run `uv run --group exact python scripts/solve_recife_exact.py` to prove and persist the new `optimal_value` and `exact_solution` certificate.
3. Update the expected `optimal_value` in `tests/test_data_loading.py` and run `uv run pytest`.
4. Refresh Phase 2 results and plots via `uv run python -m src.experiments.runner --phase 2 --tuned-config results/hpo_best_configs.json` so `results/` stays consistent with the versioned dataset.

## Risks / Trade-offs

- **[Upstream Recife Open Data CSVs or public OSRM API drift since last run]** → Verify row counts, matched stockout summary, and `data_carga` after regenerating; inspect the diff of `data/recife_ubs/recife_ubs.json` to confirm the 37 existing unique units are preserved and only the 3 duplicate USFs are replaced by 3 distinct USFs.
- **[Exact solver runtime on the new 40-unit instance could differ from 57 s]** → `scripts/solve_recife_exact.py` supports `--time-limit` (default 3600 s) and `--workers`; if needed, adjust time limit/workers while keeping full route verification and zero-gap certification mandatory.
- **[Replacement USFs may have different stockout ranges, shifting min-max scaling slightly]** → `assign_empirical_demands` automatically recomputes `raw_min`, `raw_max`, and scaled demands across all 40 unique units; `demand_metadata` will record the exact updated bounds and match counts.
