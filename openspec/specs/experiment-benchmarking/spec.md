# experiment-benchmarking Specification

## Purpose

Orchestrates reproducible multi-seed experimental suites, computes comparative metrics and statistical tests, and generates analytical visualizations and interactive maps of the routes in Recife/PE.

## Requirements

### Requirement: Multi-seed benchmark experiment execution
The system SHALL execute automated multi-seed Phase 2 experimental campaigns comparing the deterministic Greedy Baseline, Pure GA, and Memetic GA across configurable random seeds. The default Phase 2 suite SHALL consist of the three CVRPLIB tuning/benchmark instances (`A-n32-k5`, `A-n45-k6`, `A-n60-k9` — excluding `A-n80-k10`) plus the sole held-out real-world Recife/PE road-network instance (`Recife-UBS-40-road`), excluding the geodesic Haversine instance (`Recife-UBS-40-haversine`).

#### Scenario: Multi-seed campaign execution
- **WHEN** a Phase 2 experimental campaign is executed for a list of instances and `K` seeds
- **THEN** the system runs Greedy (`seed=0`), Pure GA, and Memetic GA across all `K` seeds and records for each run: instance, method, operator configuration, seed, final distance, number of vehicles used, runtime, and per-generation history

#### Scenario: Default CVRPLIB and road-only Recife/PE Phase 2 suite selection
- **WHEN** the default experimental runner loads instances for Phase 2 comparison
- **THEN** it loads `A-n32-k5`, `A-n45-k6`, `A-n60-k9`, and `Recife-UBS-40-road`, excluding `A-n80-k10` and `Recife-UBS-40-haversine` from Phase 2 runs, summary tables, statistical tests, and analytical plots

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

### Requirement: Phase 1 (Bayesian HPO) to Phase 2 benchmarking workflow
The experiment runner SHALL use Bayesian hyperparameter optimization (Optuna TPE) as Phase 1 in the Phase 1 → Phase 2 campaign, replacing Phase 1 operator ablation. Users SHALL either load pre-computed Phase 1 HPO results via `--tuned-config <path>` or run Phase 1 HPO inline before Phase 2 on `A-n32-k5`, `A-n45-k6`, and `A-n60-k9`, keeping `Recife-UBS-40-road` strictly held out from Phase 1.

#### Scenario: Running Phase 2 with pre-computed Phase 1 tuned configs
- **WHEN** the experiment runner is invoked with `--tuned-config <path>` pointing to a valid `hpo_best_configs.json` file containing both `Pure_GA` and `Memetic_GA` entries
- **THEN** Phase 2 uses the loaded `Pure_GA` and `Memetic_GA` hyperparameter configurations (including each method's operators, population size, rates, tournament size, elitism, and Memetic local search parameters) with Phase 2's `--generations` and `--phase2-seeds` budgets, without re-running Phase 1 HPO or writing legacy ablation artifacts

#### Scenario: Running default inline Phase 1 HPO before Phase 2
- **WHEN** the experiment runner is invoked without `--tuned-config` (with or without `--tune`)
- **THEN** the runner executes Phase 1 (independent Optuna TPE HPO for `Pure_GA` and `Memetic_GA` on `A-n32-k5`, `A-n45-k6`, and `A-n60-k9`, defaulting to `--hpo-trials 30`, `--hpo-seeds 3`, `--hpo-generations 100`, `--hpo-seed 42`), saves Phase 1 HPO artifacts (`hpo_best_configs.json`, `hpo_trials_pure_ga.csv`, `hpo_trials_memetic_ga.csv`) to the output directory, and passes the resulting tuned configurations into Phase 2 comparison

#### Scenario: Rejecting mutually exclusive or invalid tuned configuration inputs
- **WHEN** the experiment runner is invoked with both `--tune` and `--tuned-config`, or with a `--tuned-config` file that is missing, malformed, or lacks valid `Pure_GA` and `Memetic_GA` configurations
- **THEN** the runner exits with a clear error message before starting Phase 1 HPO or Phase 2

### Requirement: Phase 1 (HPO) and Phase 2 progress reporting and summaries
The experiment runner SHALL display live progress indicators across Phase 1 (inline HPO), Phase 2 comparison, and post-processing with run/trial counts, elapsed time, ETA, active instance or method, and latest/best metrics. It SHALL render summary tables after Phase 1 HPO and Phase 2, and SHALL support suppressing live progress via `--no-progress` without altering exported artifacts.

#### Scenario: Live progress telemetry during Phase 2 runs
- **WHEN** an experimental campaign executes Phase 2 comparison with progress enabled
- **THEN** the runner updates a live progress display after each run showing the current phase, completed/total run count and percentage, elapsed time and ETA, current instance, method and operator pair, seed progress (`i/N`), and latest/best distance (plus percentage gap when the instance defines a known optimum)

#### Scenario: Post-processing progress feedback
- **WHEN** Phase 2 completes and the runner generates convergence curves, comparative boxplots, and the interactive Recife HTML map
- **THEN** the runner displays progress status for each post-processing step and prints a final completion summary indicating the output directory

#### Scenario: End-of-phase summaries
- **WHEN** Phase 1 HPO finishes and when Phase 2 finishes benchmarking
- **THEN** the runner renders readable summary tables showing tuned hyperparameters (for Phase 1 HPO) and per-instance/method summary metrics (for Phase 2)

#### Scenario: Disabling live progress output
- **WHEN** the runner is invoked with `--no-progress` on the CLI or with progress disabled programmatically
- **THEN** live progress bars and summary tables are suppressed while all exported CSV, JSON, chart, and map files are produced identically
