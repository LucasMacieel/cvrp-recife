# experiment-benchmarking Specification

## Purpose

Orchestrates reproducible multi-seed experimental suites, computes comparative metrics and statistical tests, and generates analytical visualizations and interactive maps of the routes in Recife/PE.

## Requirements

### Requirement: Multi-seed and ablation experiment execution
The system SHALL execute automated experimental campaigns covering operator ablation (`OX` vs. `PMX`, `Swap` vs. `Inversion`) and comparison between Greedy Baseline, Pure GA, and Memetic GA across multiple configurable random seeds.

#### Scenario: Multi-seed campaign execution
- **WHEN** an experimental campaign is executed for a list of instances and `K` seeds
- **THEN** the system records for each run: instance, method, operator configuration, seed, final distance, number of vehicles used, runtime, and per-generation history

### Requirement: Aggregate metrics and statistical tests calculation
The system SHALL aggregate results by method and instance computing mean, standard deviation, best value, worst value, percentage gap relative to the known optimum (when available), and non-parametric statistical test comparing Pure GA and Memetic GA.

#### Scenario: Gap calculation on benchmark instance
- **WHEN** an instance has a positive known optimal value provided in metadata
- **THEN** the system computes the percentage gap as `((distance_obtained - optimal) / optimal) * 100` in exported tables and summaries

### Requirement: Analytical chart and interactive Recife map generation
The system SHALL generate static visual artifacts of convergence curves and result distributions (boxplots), as well as an interactive HTML map displaying the depot, UBSs/Polyclinics, and vehicle routes in the Recife/PE scenario.

#### Scenario: Recife scenario visualization export
- **WHEN** the Recife/PE scenario experiment finishes
- **THEN** the system saves convergence/comparison chart files and an interactive HTML file containing distinct markers for depot and health units and color-coded routes per vehicle
