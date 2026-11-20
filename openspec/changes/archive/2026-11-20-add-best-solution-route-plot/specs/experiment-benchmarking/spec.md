## MODIFIED Requirements

### Requirement: Analytical chart and interactive Recife map generation
The system SHALL generate static visual artifacts of convergence curves, result distributions (boxplots), and best-solution vehicle routes (`best_solution_<instance>.png`), as well as an interactive HTML map displaying the depot, UBSs/USFs, and vehicle routes in the Recife/PE scenario. Static route plots SHALL use English labels, display each vehicle route in a distinct color with unit counts and a highlighted depot marker, and support both geographic (latitude/longitude) and Euclidean coordinate instances. When rendering geographic vehicle routes on the interactive Recife HTML map or on the static best-solution route plot, the system SHALL query road-network driving geometry for each vehicle's ordered stop sequence (starting and ending at the depot) so that route polylines follow actual streets, and SHALL automatically fall back to straight-line node-to-node coordinate segments if road geometry retrieval is disabled, times out, or fails.

#### Scenario: Recife scenario visualization export
- **WHEN** the Recife/PE scenario experiment finishes
- **THEN** the system saves convergence/comparison chart files, a static best-solution route image (`best_solution_Recife-UBS-40-road.png`) for the best Memetic GA solution, and an interactive HTML file containing distinct markers for depot and health units and color-coded routes per vehicle

#### Scenario: Static best-solution route plot for geographic and Euclidean instances
- **WHEN** a static best-solution route plot is generated for an instance providing geographic coordinates (`latlon`) or Euclidean coordinates (`coords`)
- **THEN** the system saves a high-resolution PNG image displaying the depot, customer nodes, color-coded vehicle routes, total distance, route count, and a legend with per-route unit counts in English, raising a clear error if neither coordinate set is available

#### Scenario: Road-snapped route polyline rendering
- **WHEN** the interactive Recife map or static geographic best-solution route plot is generated and the road-routing service returns a valid driving geometry for a vehicle route
- **THEN** the rendered route polyline follows the returned street-level coordinates from the depot through each assigned health unit and back to the depot

#### Scenario: Graceful fallback to straight-line route segments
- **WHEN** the interactive Recife map or static geographic best-solution route plot is generated while offline, when the road-routing service returns an error or times out, or when road-geometry lookup is disabled
- **THEN** the system logs a warning (if a request failed) and renders the affected vehicle route polyline using straight-line segments connecting consecutive stop coordinates without aborting artifact generation

### Requirement: Phase 1 (HPO) and Phase 2 progress reporting and summaries
The experiment runner SHALL display live progress indicators across Phase 1 (inline HPO), Phase 2 comparison, and post-processing with run/trial counts, elapsed time, ETA, active instance or method, and latest/best metrics. It SHALL render summary tables after Phase 1 HPO and Phase 2, and SHALL support suppressing live progress via `--no-progress` without altering exported artifacts.

#### Scenario: Live progress telemetry during Phase 2 runs
- **WHEN** an experimental campaign executes Phase 2 comparison with progress enabled
- **THEN** the runner updates a live progress display after each run showing the current phase, completed/total run count and percentage, elapsed time and ETA, current instance, method and operator pair, seed progress (`i/N`), and latest/best distance (plus percentage gap when the instance defines a known optimum)

#### Scenario: Post-processing progress feedback
- **WHEN** Phase 2 completes and the runner generates convergence curves, comparative boxplots, the static best-solution Recife route plot, and the interactive Recife HTML map
- **THEN** the runner displays progress status for each of the four post-processing steps and prints a final completion summary indicating the output directory

#### Scenario: End-of-phase summaries
- **WHEN** Phase 1 HPO finishes and when Phase 2 finishes benchmarking
- **THEN** the runner renders readable summary tables showing tuned hyperparameters (for Phase 1 HPO) and per-instance/method summary metrics (for Phase 2)

#### Scenario: Disabling live progress output
- **WHEN** the runner is invoked with `--no-progress` on the CLI or with progress disabled programmatically
- **THEN** live progress bars and summary tables are suppressed while all exported CSV, JSON, chart, and map files are produced identically
