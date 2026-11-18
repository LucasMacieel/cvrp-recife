# Proposal

## Why

Although the Recife/PE CVRP optimization (`Recife-UBS-40-road`) optimizes vehicle routes using real driving distances from OSRM (`distance_matrix_road.npy`), the interactive map renderer (`generate_recife_map` in `src/experiments/map_recife.py`) connects consecutive stops directly using raw node `[lat, lon]` coordinates. As a result, `results/recife_map.html` displays straight-line ("as the crow flies") chords cutting across blocks, buildings, and waterways rather than following actual streets.

## What Changes

- Update `generate_recife_map` (`src/experiments/map_recife.py`) to query OSRM's `/route/v1/driving` endpoint (`overview=full&geometries=geojson`) for each vehicle route's ordered stop sequence (from the depot, through assigned health units, and back to the depot) and render the returned street-following polyline geometry in `folium.PolyLine`.
- Provide a graceful fallback to straight-line node-to-node `[lat, lon]` coordinates whenever OSRM is unreachable, times out, returns a non-`Ok` response, or is explicitly disabled (e.g., for offline unit tests).
- Add unit tests in `tests/test_experiments.py` covering both OSRM road-geometry rendering (with `[lon, lat]` to `[lat, lon]` coordinate flipping) and straight-line fallback behavior.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `experiment-benchmarking`: Refine the `Analytical chart and interactive Recife map generation` requirement so that vehicle routes on the interactive Recife HTML map follow actual road geometries via OSRM `/route/v1/driving`, with automatic fallback to straight-line node segments when offline or unavailable.

## Impact

- **Code**: `src/experiments/map_recife.py` (`generate_recife_map` and a helper for OSRM route geometry retrieval).
- **Tests**: `tests/test_experiments.py` (tests for OSRM GeoJSON route decoding and offline fallback).
- **Artifacts**: `results/recife_map.html` (polylines will follow Recife street geometry when regenerated with network access).
- **Dependencies**: Uses `requests` (already in `requirements.txt` and `pyproject.toml`).
