# Spec Delta

## REMOVED Requirements

### Requirement: Loading the Recife/PE geographic scenario
**Reason**: The previous requirement mandated a geodesic Haversine fallback when the road distance matrix is missing or when geodesic mode is selected, which conflicts with strictly modeling the asymmetric Recife/PE OSRM road network.
**Migration**: Replaced by `Loading the Recife/PE road-network scenario`; ensure `data/recife_ubs/distance_matrix_road.npy` is present for offline loading and that OSRM is reachable when regenerating the dataset via `scripts/prepare_recife_data.py`.

## ADDED Requirements

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
