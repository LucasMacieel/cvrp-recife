# Tasks

## 1. OpenStreetMap Basemap Rendering in Static Route Plot

- [x] 1.1 Add Web Mercator (`EPSG:3857`) projection, zoom selection, and OSM raster tile fetching/stitching helpers (`requests` + `Pillow`) in `src/experiments/plots.py`, and verify projection round-trip / tile grid bounds with unit tests in `tests/test_experiments.py`
- [x] 1.2 Update `plot_best_solution_routes()` in `src/experiments/plots.py` to accept `use_basemap: bool = True`, render geographic (`latlon`) routes, outlined unit markers, and red star depot marker aligned over the stitched OSM basemap in a clean map frame with `© OpenStreetMap contributors` attribution, bold title, and 3-column bottom legend (`Route i (N units)` and `Depot (CAF Recife)`), and fall back cleanly with a logged warning when `use_basemap=False` or tile fetching fails (while leaving Euclidean `coords` plots unchanged); verify with mocked-tile success, `use_basemap=False`, and failure-fallback unit tests in `tests/test_experiments.py`
- [x] 1.3 Update existing offline smoke/OSRM tests in `tests/test_experiments.py` to pass `use_basemap=False` where live tile requests are unintended, and verify the full `uv run pytest` suite passes offline with zero unexpected network calls

## 2. Artifact Regeneration & README Consolidation

- [x] 2.1 Regenerate `results/best_solution_Recife-UBS-40-road.png` from `results/best_solutions.json` using the updated `plot_best_solution_routes()` (with OSRM road-snapping and OSM basemap enabled) and visually inspect the generated PNG to verify street map alignment, legibility, title, attribution, and route/unit/depot legend
- [x] 2.2 Remove the manual `results/recife_map_preview.png` file and update `README.md` to reference `results/best_solution_Recife-UBS-40-road.png` as the clickable preview linking to `results/recife_map.html`, then verify no broken references to `recife_map_preview.png` remain in the repository
