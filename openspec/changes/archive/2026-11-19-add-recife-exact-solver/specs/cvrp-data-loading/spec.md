## MODIFIED Requirements

### Requirement: Loading the Recife/PE road-network scenario
The system SHALL load a static local dataset of UBSs and Polyclinics in Recife/PE containing geographic coordinates, central depot identifier, per-unit demands, fleet capacity, optional certified `optimal_value`, and the pre-computed OSRM road-network distance matrix, without depending on network access during experiment execution, and SHALL fail with an explicit error instead of falling back to geodesic Haversine distances when road-network distances are unavailable.

#### Scenario: Offline execution with pre-computed road matrix
- **WHEN** the Recife/PE scenario is loaded without an internet connection
- **THEN** the system uses the locally stored road distance matrix and unit metadata to build the normalized instance

#### Scenario: Loading optional certified optimal value
- **WHEN** the Recife/PE metadata file (`recife_ubs.json`) contains a positive numeric `optimal_value`
- **THEN** the loaded instance exposes that value as `optimal_value` so downstream benchmarking and plotting compute exact percentage optimality gaps

#### Scenario: Backward compatibility when optimal value is absent
- **WHEN** the Recife/PE metadata file (`recife_ubs.json`) omits `optimal_value` or sets it to `null`
- **THEN** the loader succeeds offline and returns a valid instance with `optimal_value` equal to `None`

#### Scenario: Missing pre-computed road distance matrix
- **WHEN** the pre-computed road distance matrix file (`distance_matrix_road.npy`) is missing from the Recife dataset directory
- **THEN** the system aborts loading with a descriptive `FileNotFoundError` rather than computing geodesic Haversine distances

#### Scenario: Dataset preparation requires complete OSRM road matrix
- **WHEN** dataset preparation queries the OSRM road-routing table service and the request fails, returns a non-`Ok` status, or contains unreachable (`null`) distance entries
- **THEN** dataset preparation aborts with a descriptive error without writing a Haversine-substituted distance matrix

## ADDED Requirements

### Requirement: Offline exact optimum computation and certificate persistence
The system SHALL provide a reproducible offline exact-solving workflow for the Recife/PE directed asymmetric CVRP instance with unconstrained fleet size. The workflow MUST independently verify route feasibility and distance consistency against the loaded distance matrix, and SHALL persist `optimal_value` and an `exact_solution` provenance certificate into `recife_ubs.json` only when global optimality is proven.

#### Scenario: Ground-truth self-check against a published CVRPLIB optimum
- **WHEN** the offline exact-solving workflow runs with self-verification enabled against `A-n32-k5`
- **THEN** the exact solver reproduces the published optimal value (`784.0`) within floating-point tolerance (`<= 1e-4`) and produces valid routes before certifying the Recife instance

#### Scenario: Certified optimal solve for the asymmetric Recife road-network instance
- **WHEN** the offline exact-solving workflow solves `Recife-UBS-40-road` to proven optimality (`gap == 0%`)
- **THEN** every returned route satisfies vehicle capacity `Q`, all 40 health units are visited exactly once, the recomputed directed route distance matches the solver objective within `1e-4` km, and `recife_ubs.json` is updated with `optimal_value` and an `exact_solution` record containing status, solver metadata, distance, dual lower bound, vehicle count, routes, runtime, and a SHA-256 fingerprint of `distance_matrix_road.npy`

#### Scenario: Unproven or time-limited solve does not write optimal_value
- **WHEN** the exact solver terminates due to a time limit or error without proving global optimality
- **THEN** the workflow reports the diagnostic status (including any best feasible distance and dual lower bound) and does not overwrite `optimal_value` in `recife_ubs.json` with an unproven value

#### Scenario: Dry-run verification without modifying dataset files
- **WHEN** the offline exact-solving workflow is invoked in dry-run mode
- **THEN** it executes the solve and independent route verification and prints the result without modifying `recife_ubs.json`
