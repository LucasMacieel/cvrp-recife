# Spec Delta

## MODIFIED Requirements

### Requirement: Loading CVRPLIB instances
The system SHALL read files in standard `.vrp` format with `EUC_2D` coordinates, customer demands, vehicle capacity, depot index, and proven optimal value (when declared via `Optimal value` in `COMMENT`), producing a normalized instance with a symmetric distance matrix. The system MUST NOT populate `optimal_value` from non-optimal upper-bound annotations such as `Best value`.

#### Scenario: Valid CVRPLIB instance
- **WHEN** a valid `.vrp` file with `DIMENSION`, `CAPACITY`, `NODE_COORD_SECTION`, `DEMAND_SECTION`, and `DEPOT_SECTION` is loaded
- **THEN** the system returns an instance with a square `N x N` distance matrix, a demands vector with zero demand at the depot, and positive capacity `Q`

#### Scenario: Instance with demand exceeding capacity
- **WHEN** a `.vrp` file contains a customer whose individual demand exceeds vehicle capacity `Q`
- **THEN** the system rejects the instance with a descriptive infeasibility error

#### Scenario: Proven optimal value parsed from COMMENT header
- **WHEN** a `.vrp` file contains a `COMMENT` header with `Optimal value: <number>` (case-insensitive)
- **THEN** the loaded instance exposes that positive numeric value as `optimal_value`

#### Scenario: Legacy best-value upper bound is not treated as optimal
- **WHEN** a `.vrp` file contains a `COMMENT` header with `Best value: <number>` and no `Optimal value:` annotation
- **THEN** the loader succeeds and sets `optimal_value` to `None` so unproven upper bounds are never reported as proven optima

#### Scenario: Versioned A-n60-k9 benchmark reports proven CVRPLIB optimum
- **WHEN** the versioned benchmark `data/cvrplib/A-n60-k9.vrp` is loaded
- **THEN** the loaded instance exposes `optimal_value` equal to `1354.0`
