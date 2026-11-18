# experiment-benchmarking Specification

## Purpose

Orchestrates reproducible multi-seed experimental suites, computes comparative metrics and statistical tests, and generates analytical visualizations and interactive maps of the routes in Recife/PE.

## Requirements

### Requirement: Multi-seed and ablation experiment execution
The system SHALL execute automated experimental campaigns covering operator ablation (`OX` vs. `PMX`, `Swap` vs. `Inversion`) and comparison between Greedy Baseline, Pure GA, and Memetic GA across multiple configurable random seeds. For the Recife/PE geographic scenario, the default Phase 2 comparison campaign SHALL execute exclusively on the road-network instance (`Recife-UBS-40-road`) rather than running an additional geodesic Haversine benchmark instance.

#### Scenario: Multi-seed campaign execution
- **WHEN** an experimental campaign is executed for a list of instances and `K` seeds
- **THEN** the system records for each run: instance, method, operator configuration, seed, final distance, number of vehicles used, runtime, and per-generation history

#### Scenario: Road-only Recife/PE Phase 2 suite selection
- **WHEN** the default experimental runner loads the Recife/PE scenario for Phase 2 comparison
- **THEN** it loads only the road-network instance (`Recife-UBS-40-road`) and excludes the geodesic Haversine instance (`Recife-UBS-40-haversine`) from Phase 2 runs, summary tables, statistical tests, and analytical plots

### Requirement: Aggregate metrics and statistical tests calculation
The system SHALL aggregate results by method and instance computing mean, standard deviation, best value, worst value, percentage gap relative to the known optimum (when available), and non-parametric statistical test comparing Pure GA and Memetic GA.

#### Scenario: Gap calculation on benchmark instance
- **WHEN** an instance has a positive known optimal value provided in metadata
- **THEN** the system computes the percentage gap as `((distance_obtained - optimal) / optimal) * 100` in exported tables and summaries

### Requirement: Analytical chart and interactive Recife map generation
The system SHALL generate static visual artifacts of convergence curves and result distributions (boxplots), as well as an interactive HTML map displaying the depot, UBSs/Polyclinics, and vehicle routes in the Recife/PE scenario. When rendering vehicle routes on the interactive Recife HTML map, the system SHALL query road-network driving geometry for each vehicle's ordered stop sequence (starting and ending at the depot) so that route polylines follow actual streets, and SHALL automatically fall back to straight-line node-to-node coordinate segments if road geometry retrieval is disabled, times out, or fails.

#### Scenario: Recife scenario visualization export
- **WHEN** the Recife/PE scenario experiment finishes
- **THEN** the system saves convergence/comparison chart files and an interactive HTML file containing distinct markers for depot and health units and color-coded routes per vehicle

#### Scenario: Road-snapped route polyline rendering
- **WHEN** the interactive Recife map is generated and the road-routing service returns a valid driving geometry for a vehicle route
- **THEN** the route polyline rendered in the HTML map follows the returned street-level coordinates from the depot through each assigned health unit and back to the depot

#### Scenario: Graceful fallback to straight-line route segments
- **WHEN** the interactive Recife map is generated while offline, when the road-routing service returns an error or times out, or when road-geometry lookup is disabled
- **THEN** the system logs a warning (if a request failed) and renders the affected vehicle route polyline using straight-line segments connecting consecutive stop coordinates without aborting map generation
