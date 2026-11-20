# Design

## Context

See `proposal.md` for motivation and scope. Currently, `plot_best_solution_routes()` in `src/experiments/plots.py` plots geographic (`latlon`) routes directly in raw `(longitude, latitude)` degrees on a white Matplotlib grid, while `results/recife_map_preview.png` is a manually captured screenshot of the Leaflet map (`results/recife_map.html`) referenced in `README.md`.

The project's Python environment already includes `matplotlib`, `requests`, and `Pillow` (`PIL`, installed with Matplotlib), and does not include `contextily` or `pyproj`.

## Goals / Non-Goals

**Goals:**
- Render geographic (`latlon`) static best-solution route plots over a real OpenStreetMap raster tile basemap with accurate Web Mercator (EPSG:3857) alignment.
- Preserve the analytical title, `tab10` route palette, road-snapped polylines, outlined unit markers, red star depot marker, and 3-column bottom legend detailing routes, unit counts, and depot (`Depot (CAF Recife)`).
- Provide clean, deterministic fallback to the existing plain lat/lon grid when `use_basemap=False` or when tile fetching fails/times out, without breaking offline execution or tests.
- Consolidate the static Recife preview to a single generated artifact (`results/best_solution_Recife-UBS-40-road.png`) and remove the manual `results/recife_map_preview.png`.

**Non-Goals:**
- Modifying the interactive Folium map (`results/recife_map.html`).
- Adding heavy GIS dependencies (`contextily`, `rasterio`, `pyproj`, `geopandas`) to `pyproject.toml`.
- Adding persistent on-disk tile caching infrastructure.

## Decisions

### 1. Pure-Python Web Mercator Projection & OSM Tile Stitching (`requests` + `Pillow`)
- **Decision**: Implement lightweight helpers in `src/experiments/plots.py` to convert `(lat, lon)` to Web Mercator meters (`EPSG:3857`), select an appropriate zoom level, fetch `256x256` PNG tiles from `https://tile.openstreetmap.org/{z}/{x}/{y}.png` with a compliant `User-Agent` header, and stitch them into a single `PIL.Image` displayed via `ax.imshow(..., extent=[mx_min, mx_max, my_min, my_max], origin="upper", zorder=1)`.
- **Rationale**: Zero new dependencies in `pyproject.toml`; avoids native binary wheel issues (`rasterio`/`GDAL`/`pyproj`); directly mirrors the lightweight `requests`-based pattern already used by `_fetch_osrm_route_geometry()` in `src/experiments/map_recife.py`.
- **Alternatives considered**:
  - `contextily`: Convenient one-liner, but pulls in `rasterio`, `geopandas`/`mercantile`, `pyproj`, and `joblib` for a single static plot.
  - Headless browser screenshot of `recife_map.html` (Playwright/Selenium): Heavy runtime dependency, harder to keep deterministic in CI/offline environments, and would still require duplicating the Matplotlib legend layout in HTML/CSS.

### 2. Automatic Zoom Selection & Bounding Padding
- **Decision**: Compute the bounding box across all plotted route/node coordinates, apply ~12% padding on each side (with a minimum span guard for single-point/tight routes), and pick the highest integer zoom level `z` (clamped to `[1, 15]`) whose covering tile grid contains at most `25` tiles (e.g., `z=13` for Recife, ~12–20 tiles). Crop the viewport via `ax.set_xlim` / `ax.set_ylim` to the padded Web Mercator bounds.
- **Rationale**: Ensures crisp street and neighborhood labels at 300 DPI for Recife while keeping HTTP requests bounded and respectful of OSM's tile usage policy.

### 3. Visual Merging & Map Frame Layout
- **Decision**:
  - When the basemap is active: plot all polylines, unit markers, and the depot star in Web Mercator meters (`EPSG:3857`) with `ax.set_aspect("equal")`; hide numeric axis ticks/labels and dashed gridlines for a clean map-preview frame; add a subtle white-backed `© OpenStreetMap contributors` attribution label in the bottom-right corner; use `linewidth=2.4` (with `alpha=0.92`) on route polylines so routes remain clearly legible over OSM road colors; place the 3-column bottom legend closely beneath the map (`bbox_to_anchor=(0.5, -0.03)`).
  - When `use_basemap=False` or tile fetching fails: fall back to the existing plain `(lon, lat)` plot with `Longitude (°)` / `Latitude (°)` labels, dashed gridlines, and `bbox_to_anchor=(0.5, -0.12)` legend placement.
  - For Euclidean (`coords`) instances: bypass basemap logic entirely.
- **Rationale**: Delivers the clean real-map look of `recife_map_preview.png` combined with the exact analytical readability and legend structure of `best_solution_Recife-UBS-40-road.png`, while preserving full backwards compatibility in fallback and Euclidean modes.

### 4. API & Caller Compatibility
- **Decision**: Add `use_basemap: bool = True` as a keyword-only parameter on `plot_best_solution_routes(...)`. Keep `src/experiments/runner.py` calling `plot_best_solution_routes(recife_road, recife_routes, recife_dist, out_dir / f"best_solution_{recife_road.name}.png")` so the default campaign automatically produces the basemap-backed PNG.
- **Rationale**: Backwards-compatible signature; existing callers and monkeypatches in `tests/test_experiments.py` continue to work, while unit tests can explicitly pass `use_basemap=False` for fast offline execution.

## Risks / Trade-offs

- **OSM tile server rate limits or offline execution** → Mitigated by setting a descriptive `User-Agent` header, capping tile count (`<= 25` tiles per plot), applying a short per-tile timeout (`5.0s`), and automatically falling back to the plain coordinate plot with a logged warning on any failure.
- **Route color contrast against colorful OSM basemap** → Mitigated by using slightly thicker, high-opacity polylines (`linewidth=2.4`, `alpha=0.92`) and black-outlined circular markers (`edgecolors="black"`), plus slight basemap softening (`alpha=0.90`) if needed for readability.
- **Existing tests making accidental live tile requests** → Mitigated by passing `use_basemap=False` in existing offline smoke/OSRM tests and adding dedicated mocked-tile unit tests in `tests/test_experiments.py`.
