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

### Requirement: Run-level experiment progress reporting and summaries
The experiment runner SHALL display live run-level progress indicators across Phase 1 ablation, Phase 2 comparison, and post-processing (plots and Recife map), showing completed/total runs, percentage, elapsed time, ETA, active instance, method or operators, seed (`i/N`), and latest/best distance (with optimal gap% when known). It SHALL render concise phase summaries after Phase 1 and Phase 2, and SHALL support disabling live progress via `--no-progress` without altering exported artifacts.

#### Scenario: Live progress telemetry during Phase 1 and Phase 2 runs
- **WHEN** an experimental campaign executes Phase 1 ablation or Phase 2 comparison with progress enabled
- **THEN** the runner updates a live progress display after each run showing the current phase, completed/total run count and percentage, elapsed time and ETA, current instance, method or operator pair, seed progress (`i/N`), and latest/best distance (plus percentage gap when the instance defines a known optimum)

#### Scenario: Post-processing progress feedback
- **WHEN** Phase 2 completes and the runner generates convergence curves, comparative boxplots, and the interactive Recife HTML map
- **THEN** the runner displays progress status for each post-processing step and prints a final completion summary indicating the output directory

#### Scenario: End-of-phase summaries
- **WHEN** Phase 1 ablation finishes operator selection and when Phase 2 finishes benchmarking
- **THEN** the runner renders a readable summary table showing the selected operators (for Phase 1) and per-instance/method summary metrics (for Phase 2)

#### Scenario: Disabling live progress output
- **WHEN** the runner is invoked with `--no-progress` on the CLI or with progress disabled programmatically
- **THEN** live progress bars are suppressed while all exported CSV, JSON, chart, and map files are produced identically

### Requirement: Optional tuned hyperparameter integration in Phase 2 benchmarking
The experiment runner SHALL support running Phase 2 comparison with per-method tuned hyperparameters for Pure GA and Memetic GA either by loading a previously exported HPO configuration file via `--tuned-config <path>` or by executing HPO inline before Phase 2 via `--tune` (with configurable `--hpo-trials` and `--hpo-seeds`). When neither flag is supplied, the runner SHALL preserve its default Phase 1 ablation followed by Phase 2 comparison behavior unchanged.

#### Scenario: Running Phase 2 with a pre-computed tuned configuration file
- **WHEN** the experiment runner is invoked with `--tuned-config <path>` pointing to a valid `hpo_best_configs.json` file
- **THEN** Phase 2 uses the loaded `Pure_GA` and `Memetic_GA` hyperparameter configurations (including each method's operators, population size, rates, tournament size, elitism, and Memetic local search parameters) instead of uniform CLI defaults, and skips Phase 1 operator ablation

#### Scenario: Running inline HPO before Phase 2 via --tune
- **WHEN** the experiment runner is invoked with `--tune`
- **THEN** the runner executes hyperparameter optimization for Pure GA and Memetic GA on the tuning subset, saves HPO artifacts to the output directory, and passes the resulting tuned configurations into Phase 2 comparison

#### Scenario: Rejecting mutually exclusive or invalid tuned configuration inputs
- **WHEN** the experiment runner is invoked with both `--tune` and `--tuned-config`, or with a `--tuned-config` file that is missing or fails schema validation
- **THEN** the runner exits with a clear error message before starting Phase 2

#### Scenario: Default behavior without HPO flags
- **WHEN** the experiment runner is invoked without `--tune` or `--tuned-config`
- **THEN** it executes Phase 1 operator ablation followed by Phase 2 comparison with the default/CLI-specified hyperparameters, maintaining full backward compatibility
