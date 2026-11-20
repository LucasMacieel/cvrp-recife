# Spec Delta

## MODIFIED Requirements

### Requirement: Analytical chart and interactive Recife map generation
The system SHALL generate static visual artifacts of convergence curves, result distributions (boxplots), and best-solution vehicle routes (`best_solution_<instance>.png`), as well as an interactive HTML map displaying the depot, UBSs/USFs, and vehicle routes in the Recife/PE scenario. Static route plots SHALL use English labels, display each vehicle route in a distinct color with unit counts and a highlighted depot marker, and support both geographic (latitude/longitude) and Euclidean coordinate instances. When rendering geographic vehicle routes on the interactive Recife HTML map or on the static best-solution route plot, the system SHALL query road-network driving geometry for each vehicle's ordered stop sequence (starting and ending at the depot) so that route polylines follow actual streets, and SHALL automatically fall back to straight-line node-to-node coordinate segments if road geometry retrieval is disabled, times out, or fails. For static geographic best-solution route plots, the system SHALL also render the routes over a real OpenStreetMap raster tile basemap with OpenStreetMap attribution in a clean map frame while preserving the title, color-coded routes, outlined unit markers, depot marker, and bottom legend detailing routes, per-route unit counts, and depot; it SHALL automatically fall back to a plain geographic coordinate plot if basemap tile retrieval is disabled, times out, or fails.

#### Scenario: Recife scenario visualization export
- **WHEN** the Recife/PE scenario experiment finishes
- **THEN** the system saves convergence/comparison chart files, a static best-solution route image (`best_solution_Recife-UBS-40-road.png`) for the best Memetic GA solution rendered over an OpenStreetMap basemap with the route/unit/depot legend, and an interactive HTML file containing distinct markers for depot and health units and color-coded routes per vehicle

#### Scenario: Static best-solution route plot for geographic and Euclidean instances
- **WHEN** a static best-solution route plot is generated for an instance providing geographic coordinates (`latlon`) or Euclidean coordinates (`coords`)
- **THEN** the system saves a high-resolution PNG image displaying the depot, customer nodes, color-coded vehicle routes, total distance, route count, and a legend with per-route unit counts in English, raising a clear error if neither coordinate set is available

#### Scenario: Geographic static route plot with OpenStreetMap basemap
- **WHEN** a static best-solution route plot is generated for a geographic (`latlon`) instance with basemap rendering enabled and map tiles are retrieved successfully
- **THEN** the system renders the road-snapped routes, outlined unit markers, and highlighted depot marker aligned over the OpenStreetMap basemap with OpenStreetMap attribution, title, and bottom legend detailing each route's unit count and the depot

#### Scenario: Graceful fallback when basemap tiles are disabled or unavailable
- **WHEN** a static best-solution route plot is generated for a geographic (`latlon`) instance with basemap rendering disabled, while offline, or when map tile retrieval fails or times out
- **THEN** the system logs a warning (if tile retrieval failed) and renders the static route plot on a plain latitude/longitude coordinate grid without aborting artifact generation, and performs no tile requests for Euclidean (`coords`) instances

#### Scenario: Road-snapped route polyline rendering
- **WHEN** the interactive Recife map or static geographic best-solution route plot is generated and the road-routing service returns a valid driving geometry for a vehicle route
- **THEN** the rendered route polyline follows the returned street-level coordinates from the depot through each assigned health unit and back to the depot

#### Scenario: Graceful fallback to straight-line route segments
- **WHEN** the interactive Recife map or static geographic best-solution route plot is generated while offline, when the road-routing service returns an error or times out, or when road-geometry lookup is disabled
- **THEN** the system logs a warning (if a request failed) and renders the affected vehicle route polyline using straight-line segments connecting consecutive stop coordinates without aborting artifact generation
