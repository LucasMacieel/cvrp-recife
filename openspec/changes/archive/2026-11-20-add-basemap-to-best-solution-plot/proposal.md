# Proposal

## Why

The project currently maintains two separate static visualizations of the Recife/PE routing solution: `results/best_solution_Recife-UBS-40-road.png` (programmatically generated with a descriptive title, color-coded routes, depot star marker, and per-route unit-count legend, but drawn on an empty lat/lon grid with no geographic context) and `results/recife_map_preview.png` (a manual screenshot of the Leaflet map showing real OpenStreetMap streets, but lacking a title, legend, and automated regeneration). Merging the real OpenStreetMap basemap into `plot_best_solution_routes()` delivers a single, reproducible, publication-ready map preview with full route, unit, and depot legend details.

## What Changes

- Enhance `plot_best_solution_routes()` in `src/experiments/plots.py` to render geographic (`latlon`) best-solution routes over a real OpenStreetMap raster tile basemap while retaining the bold title (method, instance, total distance, route count), color-coded road-snapped polylines, outlined unit markers, red star depot marker, bottom legend detailing routes, unit counts, and depot (`Depot (CAF Recife)`), and OpenStreetMap attribution.
- Add a `use_basemap: bool = True` keyword parameter to `plot_best_solution_routes()` with automatic graceful fallback: when tile fetching is disabled, offline, times out, or fails, log a warning (on failure) and fall back to the plain geographic coordinate plot without aborting artifact generation.
- Keep Euclidean (`coords`) instance plotting behavior unchanged (no basemap tile requests).
- Regenerate `results/best_solution_Recife-UBS-40-road.png` using the merged real-map + legend style from `results/best_solutions.json`.
- Remove the manual `results/recife_map_preview.png` image and update `README.md` to reference `results/best_solution_Recife-UBS-40-road.png` as the clickable preview linking to `results/recife_map.html`.
- Keep the interactive Folium map (`results/recife_map.html`) unchanged.

## Capabilities

### New Capabilities

### Modified Capabilities
- `experiment-benchmarking`: Update the static geographic best-solution route plot requirement to render routes over a real OpenStreetMap tile basemap with map attribution and automatic graceful fallback to a plain coordinate plot when basemap retrieval is disabled or unavailable, while preserving the title, route colors, depot marker, and per-route unit-count legend.

## Impact

- **Code**: `src/experiments/plots.py` (Web Mercator projection and OSM tile fetching/stitching using already-installed `requests`, `Pillow`, and `matplotlib`; no new dependencies needed in `pyproject.toml`).
- **Tests**: `tests/test_experiments.py` (mocked basemap tile rendering, `use_basemap=False`, and tile-fetch failure fallback tests; existing offline smoke tests updated to pass `use_basemap=False` where appropriate).
- **Artifacts & Docs**: `results/best_solution_Recife-UBS-40-road.png` regenerated, `results/recife_map_preview.png` removed, and `README.md` updated to point the Recife map preview link to `results/best_solution_Recife-UBS-40-road.png`.
