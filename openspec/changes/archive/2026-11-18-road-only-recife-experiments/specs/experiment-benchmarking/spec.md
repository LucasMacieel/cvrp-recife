# Spec Delta

## MODIFIED Requirements

### Requirement: Multi-seed and ablation experiment execution
The system SHALL execute automated experimental campaigns covering operator ablation (`OX` vs. `PMX`, `Swap` vs. `Inversion`) and comparison between Greedy Baseline, Pure GA, and Memetic GA across multiple configurable random seeds. For the Recife/PE geographic scenario, the default Phase 2 comparison campaign SHALL execute exclusively on the road-network instance (`Recife-UBS-40-road`) rather than running an additional geodesic Haversine benchmark instance.

#### Scenario: Multi-seed campaign execution
- **WHEN** an experimental campaign is executed for a list of instances and `K` seeds
- **THEN** the system records for each run: instance, method, operator configuration, seed, final distance, number of vehicles used, runtime, and per-generation history

#### Scenario: Road-only Recife/PE Phase 2 suite selection
- **WHEN** the default experimental runner loads the Recife/PE scenario for Phase 2 comparison
- **THEN** it loads only the road-network instance (`Recife-UBS-40-road`) and excludes the geodesic Haversine instance (`Recife-UBS-40-haversine`) from Phase 2 runs, summary tables, statistical tests, and analytical plots
