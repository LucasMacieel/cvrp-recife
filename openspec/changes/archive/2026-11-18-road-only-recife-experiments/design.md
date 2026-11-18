# Design

## Context

See `proposal.md` (`Why`), `specs/cvrp-data-loading/spec.md`, and `specs/experiment-benchmarking/spec.md` for motivation and requirements. Currently, geodesic Haversine distances appear in three places:
1. `src/data/recife_loader.py` exposes `compute_haversine_matrix()` and `load_recife(data_dir, mode="road" | "haversine")`, silently falling back to Haversine whenever `distance_matrix_road.npy` is absent.
2. `scripts/prepare_recife_data.py` defines `haversine_km()` and substitutes Haversine distances both for `None` cells in OSRM responses and as a full-matrix fallback if OSRM fails.
3. `src/experiments/runner.py` defines `load_recife_suite()` returning both `mode="road"` and `mode="haversine"` instances for Phase 2.

Because the Recife/PE study strictly models the real asymmetric urban road network (`distance_matrix_road.npy` from OSRM), all Haversine modes and fallbacks must be removed in favor of explicit fail-fast errors when OSRM road distances are unavailable.

## Goals / Non-Goals

**Goals:**
- Strictly enforce the pre-computed OSRM road-network matrix (`distance_matrix_road.npy`) in `src/data/recife_loader.py` with no Haversine mode or fallback.
- Fail fast in `scripts/prepare_recife_data.py` if OSRM fails, returns non-`Ok`, or returns any unreachable (`None`) cell, preventing silent geodesic contamination of `distance_matrix_road.npy`.
- Execute Phase 2 experiments over the 5-instance suite (`A-n32-k5`, `A-n45-k6`, `A-n60-k9`, `A-n80-k10`, and `Recife-UBS-40-road`).
- Keep tracked outputs in `results/`, automated tests, and `README.md` consistent with the strict road-only Recife setup.

**Non-Goals:**
- Modifying `src/experiments/map_recife.py`'s offline straight-line map-rendering fallback (which affects only HTML polyline visualization when offline, not optimization distance matrices).
- Changing which 40 UBS/USF units are selected or altering empirical stockout demand estimation in `scripts/prepare_recife_data.py`.
- Altering GA hyperparameters, random seeds, or evolutionary/local-search operators.

## Decisions

### 1. Strict OSRM road-only loader API (`load_recife`)
- **Choice**: Remove `compute_haversine_matrix()` and the `mode` parameter from `load_recife(data_dir: str | Path = "data/recife_ubs") -> CVRPInstance` in `src/data/recife_loader.py`. Always load `distance_matrix_road.npy`, raising `FileNotFoundError(f"Recife road distance matrix not found: {road_path}")` if absent, and retain the instance name `f"{payload.get('name', 'Recife-UBS')}-road"` (`Recife-UBS-40-road`).
- **Rationale**: Eliminates silent geodesic fallback and prevents callers from accidentally optimizing over a symmetric Haversine grid, while keeping `Recife-UBS-40-road` consistent with existing result filenames and benchmark tables.
- **Alternatives considered**: Keeping `mode="road"` as a single-value parameter; rejected as dead API surface once `mode="haversine"` is removed.

### 2. Fail-fast OSRM matrix acquisition in dataset preparation
- **Choice**: Remove `haversine_km()` from `scripts/prepare_recife_data.py`. Update `_fetch_osrm_matrix(latlon: np.ndarray) -> np.ndarray` to raise a descriptive `RuntimeError` if the OSRM request fails, returns `code != "Ok"`, lacks `"distances"`, or contains any `None` (unreachable) entry, and remove the `if road_matrix is None:` Haversine fallback block in `main()`.
- **Rationale**: Guarantees that `data/recife_ubs/distance_matrix_road.npy` never silently contains mixed or fully geodesic Haversine distances.
- **Alternatives considered**: Keeping per-cell Haversine imputation for `None` entries; rejected to strictly enforce that every pairwise distance in the Recife matrix comes from the OSRM road network.

### 3. Keep `load_recife_suite()` returning a road-only list
- **Choice**: Update `load_recife_suite(data_dir="data/recife_ubs")` in `src/experiments/runner.py` to return `[load_recife(data_dir)]`.
- **Rationale**: Preserves the `list[CVRPInstance]` return contract so `main()` continues to compose `p2_instances = cvrplib_instances + recife_instances` and select `recife_road = recife_instances[0]` without structural changes.
- **Alternatives considered**: Removing `load_recife_suite()` entirely; rejected to keep `runner.py` suite loaders symmetric (`load_cvrplib_suite`, `load_recife_suite`).

### 4. Clean stale Haversine files and regenerate `results/`
- **Choice**: Explicitly delete tracked `results/boxplot_Recife-UBS-40-haversine.png` and `results/convergence_Recife-UBS-40-haversine.png` and regenerate Phase 1/2 outputs via `python -m src.experiments.runner`.
- **Rationale**: `runner.py` and `plots.py` only overwrite files for active instances and do not prune legacy outputs from prior runs. Deterministic per-instance seeding ensures all CVRPLIB and `Recife-UBS-40-road` metrics remain unchanged while producing clean 5-instance CSV/JSON artifacts.
- **Alternatives considered**: Manually editing CSV/JSON result files; rejected to preserve end-to-end reproducibility.

## Risks / Trade-offs

- **[Risk] Breaking callers passing `mode=...` to `load_recife()`** → **Mitigation**: Update all in-repo call sites (`src/experiments/runner.py`, `tests/test_data_loading.py`, `tests/test_experiments.py`) and document the breaking change clearly in `proposal.md` and `README.md`.
- **[Risk] Re-running `scripts/prepare_recife_data.py` fails when public OSRM is unreachable** → **Mitigation**: Keep the pre-computed `data/recife_ubs/distance_matrix_road.npy` versioned in git so all experiment runs and tests remain 100% offline-reproducible without invoking `prepare_recife_data.py`.
- **[Risk] Stale Haversine PNGs left behind in `results/`** → **Mitigation**: Explicitly delete both Haversine PNG files and verify `results/` contains exactly 5 `boxplot_*.png` and 5 `convergence_*.png` files after regeneration.
- **[Risk] Offline OSRM fallback during `runner.py` map regeneration** → **Mitigation**: Verify `results/recife_map.html` retains dense road-snapped `L.polyline` coordinate arrays after running `runner.py` (or preserve the previously generated road-snapped `recife_map.html` if OSRM is unreachable during regeneration).
