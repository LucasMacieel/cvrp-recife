# cvrp-data-loading Specification

## Purpose

Loads, validates, and normalizes CVRP problem instances from standard CVRPLIB files and the geographic dataset of Primary Health Units (UBSs/Polyclinics) in Recife/PE into a unified format of distance matrix, demands, and capacity.

## Requirements

### Requirement: Loading CVRPLIB instances
The system SHALL read files in standard `.vrp` format with `EUC_2D` coordinates, customer demands, vehicle capacity, depot index, and known optimal value (when available), producing a normalized instance with a symmetric distance matrix.

#### Scenario: Valid CVRPLIB instance
- **WHEN** a valid `.vrp` file with `DIMENSION`, `CAPACITY`, `NODE_COORD_SECTION`, `DEMAND_SECTION`, and `DEPOT_SECTION` is loaded
- **THEN** the system returns an instance with a square `N x N` distance matrix, a demands vector with zero demand at the depot, and positive capacity `Q`

#### Scenario: Instance with demand exceeding capacity
- **WHEN** a `.vrp` file contains a customer whose individual demand exceeds vehicle capacity `Q`
- **THEN** the system rejects the instance with a descriptive infeasibility error

### Requirement: Loading the Recife/PE geographic scenario
The system SHALL load a static local dataset of UBSs and Polyclinics in Recife/PE containing geographic coordinates, central depot identifier, per-unit demands, fleet capacity, and pre-computed distance matrix, without depending on network access during experiment execution.

#### Scenario: Offline execution with pre-computed road matrix
- **WHEN** the Recife/PE scenario is loaded without an internet connection
- **THEN** the system uses the locally stored road distance matrix and unit metadata to build the normalized instance

#### Scenario: Geodesic fallback via Haversine
- **WHEN** a pre-computed distance matrix is missing or the geodesic distance mode is explicitly selected for geographic coordinates
- **THEN** the system computes the distance matrix using the Haversine formula in kilometers

### Requirement: Normalized instance integrity validation
The system SHALL validate every loaded instance before optimization, ensuring dimensional consistency between distance matrix, coordinates, and demands, absence of negative or missing (`NaN`) values, and presence of at least one customer besides the depot.

#### Scenario: Distance matrix incompatible with node count
- **WHEN** the provided distance matrix does not have `N x N` dimensions matching the demands vector
- **THEN** the system aborts loading and reports the dimensional inconsistency
