# Design

## Context

See `proposal.md` for motivation. Currently, `scripts/prepare_recife_data.py` fetches an $N \times N$ scalar distance matrix from OSRM's `/table/v1/driving` endpoint and saves `data/recife_ubs/distance_matrix_road.npy`, while `generate_recife_map` in `src/experiments/map_recife.py` receives only the `CVRPInstance` (with node `latlon`) and `routes` (lists of customer node indices). It constructs `path_coords = [[depot_lat, depot_lon], ..., [depot_lat, depot_lon]]` directly from node coordinates and passes them to `folium.PolyLine`.

In the Recife dataset (`Recife-UBS-40-road`), a solution typically has ~8 vehicle routes with 3–6 customer stops per route (5–8 waypoints per vehicle including the depot at both ends).

## Goals / Non-Goals

**Goals:**
- Render street-following polylines for each vehicle route in `results/recife_map.html` by querying OSRM's `/route/v1/driving` API per vehicle route.
- Preserve offline resilience and deterministic testing via automatic fallback to straight-line node coordinates on any network/API error and an optional `use_osrm: bool = True` parameter.

**Non-Goals:**
- Altering `data/recife_ubs/distance_matrix_road.npy` or solver distance evaluation (`CVRPInstance.distance_matrix` remains authoritative for optimization).
- Precomputing or caching all $N \times (N - 1)$ pairwise edge polylines on disk.
- Client-side browser routing (e.g., Leaflet Routing Machine).

## Decisions

### 1. Query OSRM `/route/v1/driving` per vehicle route at map generation time
- **Choice**: For each non-empty route, construct the full ordered sequence of node indices `[depot, *route, depot]`, format coordinates as `{lon:.6f},{lat:.6f}` separated by `;`, and query:
  `https://router.project-osrm.org/route/v1/driving/{coords}?overview=full&geometries=geojson`
- **Rationale**: Requires only one HTTP GET request per vehicle (~8 requests total for `Recife-UBS-40-road`) with full street resolution (`overview=full`) and avoids polyline encoding dependencies by requesting `geometries=geojson`.
- **Alternatives considered**:
  - *Precomputing pairwise edge geometries in `prepare_recife_data.py`*: Keeps map generation 100% offline, but requires fetching/storing up to $41 \times 40 = 1{,}640$ directed edge geometries.
  - *Client-side JS routing in HTML*: Breaks when viewing `recife_map.html` offline and exposes the viewer to public OSRM demo server rate limits on every page load.

### 2. Coordinate ordering conversion (`[lon, lat]` $\rightarrow$ `[lat, lon]`)
- **Choice**: Extract `payload["routes"][0]["geometry"]["coordinates"]` from the OSRM GeoJSON response and convert each `[lon, lat]` pair to `[float(lat), float(lon)]` before passing to `folium.PolyLine`.
- **Rationale**: OSRM and GeoJSON use `[longitude, latitude]` ordering, whereas Leaflet and `folium.PolyLine` expect `[latitude, longitude]`.

### 3. Graceful fallback and testability (`use_osrm: bool = True`)
- **Choice**: Wrap the OSRM request in a helper function (e.g., `_fetch_osrm_route_geometry(waypoints_latlon, timeout=10) -> list[list[float]] | None`). If `use_osrm=False`, or if `requests.get` raises an exception, times out, returns a non-200 status, or returns `code != "Ok"`, fall back to the raw `waypoints_latlon` list.
- **Rationale**: Ensures `generate_recife_map` never fails when offline or during CI/unit tests, while allowing targeted unit tests with mocked `requests.get` responses.

## Risks / Trade-offs

- **[Risk] Public OSRM demo server unavailability or transient timeout during `runner.py`** $\rightarrow$ **Mitigation**: Use a bounded timeout (e.g., 10 seconds) per request, catch `requests.RequestException` / JSON parsing errors, emit a warning, and fall back to straight-line node segments for that route so experiment results and HTML map generation always succeed.
- **[Risk] Minor visual discrepancy if OSRM's live road network changes relative to static `distance_matrix_road.npy`** $\rightarrow$ **Mitigation**: Waypoints are pinned to exact stop coordinates `[depot, *route, depot]`, so route visitation order and stop markers remain strictly faithful to the solver's solution.
