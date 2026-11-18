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

### Requirement: Loading the Recife/PE road-network scenario
The system SHALL load a static local dataset of UBSs and Polyclinics in Recife/PE containing geographic coordinates, central depot identifier, per-unit demands, fleet capacity, and the pre-computed OSRM road-network distance matrix, without depending on network access during experiment execution, and SHALL fail with an explicit error instead of falling back to geodesic Haversine distances when road-network distances are unavailable.

#### Scenario: Offline execution with pre-computed road matrix
- **WHEN** the Recife/PE scenario is loaded without an internet connection
- **THEN** the system uses the locally stored road distance matrix and unit metadata to build the normalized instance

#### Scenario: Missing pre-computed road distance matrix
- **WHEN** the pre-computed road distance matrix file (`distance_matrix_road.npy`) is missing from the Recife dataset directory
- **THEN** the system aborts loading with a descriptive `FileNotFoundError` rather than computing geodesic Haversine distances

#### Scenario: Dataset preparation requires complete OSRM road matrix
- **WHEN** dataset preparation queries the OSRM road-routing table service and the request fails, returns a non-`Ok` status, or contains unreachable (`null`) distance entries
- **THEN** dataset preparation aborts with a descriptive error without writing a Haversine-substituted distance matrix

### Requirement: Normalized instance integrity validation
The system SHALL validate every loaded instance before optimization, ensuring dimensional consistency between distance matrix, coordinates, and demands, absence of negative or missing (`NaN`) values, and presence of at least one customer besides the depot.

#### Scenario: Distance matrix incompatible with node count
- **WHEN** the provided distance matrix does not have `N x N` dimensions matching the demands vector
- **THEN** the system aborts loading and reports the dimensional inconsistency

### Requirement: Data-driven Recife replenishment demand estimation
The dataset preparation workflow SHALL derive per-unit replenishment demands for Recife/PE health units (UBSs and USFs) by cross-referencing the base health unit network against municipal pharmacy stock records (`medicamentos-por-unidade-de-saude.csv`) from the Recife Open Data Portal, computing each matched unit's raw demand proxy as the count of inventory items with zero available quantity (`quantidade = 0`).

#### Scenario: Primary linkage by US unit code
- **WHEN** a health unit's official name and a pharmacy stock record share the same `US <number>` unit code
- **THEN** the unit is linked to that pharmacy stock record and its raw replenishment proxy equals the number of items at that unit with `quantidade = 0`

#### Scenario: Fallback linkage by normalized unit name and bairro
- **WHEN** a health unit cannot be matched via its `US <number>` code, but matches a pharmacy stock record after stripping accents and case from the unit name combined with `bairro`
- **THEN** the unit is linked to that stock record and its raw replenishment proxy equals the matched stockout count

#### Scenario: Fallback imputation for units absent from pharmacy stock records
- **WHEN** a health unit matches neither by `US <number>` code nor by normalized unit name and `bairro`
- **THEN** the system assigns the median raw stockout count of matched units of the same unit type (`UBS` or `USF`), or the overall matched median if no units of that type were matched

#### Scenario: Decimal-formatted zero quantities in stock records
- **WHEN** pharmacy stock records represent zero stock using locale decimal formatting (such as `"0,0"` or `"0.0"`)
- **THEN** those records are counted as stockouts (`quantidade = 0`) alongside integer `"0"` records

### Requirement: CVRP-feasible demand normalization and static dataset persistence
The dataset preparation workflow SHALL normalize customer raw stockout counts into bounded integer CVRP demands `[d_min, d_max]` using min-max scaling while preserving `demand = 0` for the central depot (`DEPOT-CAF`) and enforcing `1 <= d_i <= capacity` for every customer node, and SHALL persist both scaled demands and raw stockout provenance metadata into the local static dataset so that offline loading and experiments remain deterministic without network access.

#### Scenario: Min-max integer scaling across varying stockout counts
- **WHEN** customer units have raw stockout counts with `min(x) < max(x)` and scaling bounds `[d_min, d_max]` satisfying `1 <= d_min <= d_max <= capacity`
- **THEN** each customer receives an integer demand `d_i = round(d_min + ((x_i - min(x)) / (max(x) - min(x))) * (d_max - d_min))`, with the lowest-stockout customer(s) mapped to `d_min`, the highest-stockout customer(s) mapped to `d_max`, and the depot assigned `demand = 0`

#### Scenario: Degenerate constant stockout counts across all units
- **WHEN** all customer units have identical raw stockout counts (`min(x) == max(x)`)
- **THEN** scaling completes without division-by-zero error and assigns every customer a valid integer demand within `[d_min, d_max]`

#### Scenario: Invalid scaling bounds rejected
- **WHEN** configured scaling bounds violate `1 <= d_min <= d_max <= capacity`
- **THEN** dataset preparation fails with a descriptive validation error before writing the static dataset

#### Scenario: Offline loader compatibility with enriched static dataset
- **WHEN** the Recife/PE dataset is regenerated with scaled empirical demands and per-node raw metadata (`raw_stockouts`, `total_items`) and subsequently loaded offline
- **THEN** the offline loader constructs a valid `CVRPInstance` with `int64` demands, `demands[depot] == 0`, `1 <= demands[i] <= capacity` for all customers, and requires no network access
