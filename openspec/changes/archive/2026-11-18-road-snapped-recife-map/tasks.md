# Tasks

## 1. OSRM Route Geometry Rendering & Fallback

- [x] 1.1 Implement an OSRM `/route/v1/driving` helper in `src/experiments/map_recife.py` (`overview=full&geometries=geojson`) that converts GeoJSON `[lon, lat]` coordinates to `[lat, lon]` and returns `None` on network errors, timeouts, or non-`Ok` responses, and verify unit tests for coordinate conversion and error handling pass.
- [x] 1.2 Update `generate_recife_map` in `src/experiments/map_recife.py` with an optional `use_osrm: bool = True` parameter so each vehicle route queries road-snapped geometry and falls back to straight-line stop coordinates when `use_osrm=False` or when the helper returns `None`, and verify `pytest tests/test_experiments.py` passes with tests covering both mocked OSRM road geometry and straight-line fallback.

## 2. Artifact Regeneration & Integration Check

- [x] 2.1 Regenerate `results/recife_map.html` from the saved `Recife-UBS-40-road` best solution in `results/best_solutions.json` and verify the generated HTML contains dense road-snapped `L.polyline` coordinate sequences rather than only stop-count vertices.
