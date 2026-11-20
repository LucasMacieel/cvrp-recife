# Design

## Context

See `proposal.md` for motivation. Previously, `src/experiments/plots.py` generated only `convergence_*.png` and `boxplot_*.png`, while `src/experiments/map_recife.py` generated the interactive `recife_map.html` using `_fetch_osrm_route_geometry` for road-snapped polylines. The post-processing stage in `src/experiments/runner.py` (`run_post_processing`) executed three steps (`plot_convergence_curves`, `plot_comparative_boxplots`, `generate_recife_map`), leaving static best-solution route visualization outside the reproducible pipeline.

## Goals / Non-Goals

**Goals:**
- Provide a single reusable Matplotlib route plotter (`plot_best_solution_routes`) in `src/experiments/plots.py` that produces high-resolution (300 DPI) static PNG figures with English labels.
- Reuse the existing OSRM route-geometry helper (`_fetch_osrm_route_geometry`) so static geographic plots match the street-following paths of `recife_map.html` and inherit the same timeout/error fallback behavior.
- Integrate static best-solution route generation directly into `run_post_processing` for `Recife-UBS-40-road` without adding new external dependencies or breaking offline tests.

**Non-Goals:**
- Changing language conventions for repository outputs (all repository charts remain in English; localized paper figures live separately outside the automated code outputs).
- Modifying solver logic, Phase 1 HPO, Phase 2 benchmarking metrics, or `best_solutions.json` schema.
- Adding a separate CLI entrypoint solely for plotting (the function is callable programmatically and invoked automatically during post-processing).

## Decisions

1. **Reuse `_fetch_osrm_route_geometry` from `src.experiments.map_recife` rather than duplicating HTTP/GeoJSON parsing**:
   - *Rationale*: Keeps OSRM endpoint URL, timeout handling, `[lon, lat]`-to-`[lat, lon]` conversion, and warning logs in one place so both `recife_map.html` and `best_solution_Recife-UBS-40-road.png` behave identically online and offline.
   - *Alternative considered*: Moving `_fetch_osrm_route_geometry` into a new shared module. Rejected as unnecessary churn for a single helper with existing monkeypatched tests targeting `src.experiments.map_recife.requests.get`.

2. **Support both `latlon` (geographic) and `coords` (Euclidean) in `plot_best_solution_routes`**:
   - *Rationale*: While `run_post_processing` currently renders `Recife-UBS-40-road` (`latlon`), allowing `coords` fallback makes the plotter usable on CVRPLIB instances too with minimal extra code, raising `ValueError` only if neither is populated.
   - *Alternative considered*: Restricting strictly to `latlon`. Rejected because CVRPLIB instances already carry `coords` on `CVRPInstance`.

3. **Visual layout matching the project's analytical figures**:
   - *Rationale*: Uses Matplotlib's `tab10` colormap (`cmap(v_idx % 10)`), equal data aspect ratio (`set_aspect("equal", adjustable="datalim")`), black-edged customer markers, red star depot marker, 3-column bottom legend (`Route k (m units)` and `Depot (...)`), dashed grid (`alpha=0.4`), and `dpi=300, bbox_inches="tight"`.

4. **Keep `use_osrm: bool = True` by default, disabled or mocked in unit tests**:
   - *Rationale*: Automated post-processing produces road-snapped routes when online and falls back cleanly when offline, while unit tests pass `use_osrm=False` or monkeypatch `plot_best_solution_routes` to guarantee fast, deterministic offline execution.

## Risks / Trade-offs

- **OSRM public API availability or latency during post-processing** → Mitigated by the 10s per-route timeout and automatic fallback to straight-line node segments inside `_fetch_osrm_route_geometry`.
- **Subtle visual differences if OSRM updates underlying OSM road geometry over time** → Mitigated by deterministic route sequences stored in `results/best_solutions.json`; route topology and total distance remain fixed to the static `distance_matrix_road.npy`.
