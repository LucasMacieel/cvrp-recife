# Spec Delta

## ADDED Requirements

### Requirement: Cross-dataset deduplication and unique unit identification
The Recife/PE dataset preparation workflow SHALL deduplicate physical health units across the municipal UBS and USF datasets so that each selected customer node represents a distinct physical facility with a unique identifier, and the offline Recife/PE loader SHALL reject static datasets containing duplicate node identifiers.

#### Scenario: Cross-dataset duplicate with shifted coordinates and shared US code
- **WHEN** a health unit appears in both the UBS and USF datasets with the same canonical `US <number>` code (such as `US 155`, `US 121`, or `US 137`) even when its coordinates differ by tens of meters or its USF CNES is a placeholder
- **THEN** dataset preparation retains the first-ingested (UBS) entry, skips the duplicate USF entry, and selects the next distinct USF from the round-robin RPA pool so the target customer count consists of distinct physical units

#### Scenario: Cross-dataset duplicate sharing a valid CNES code
- **WHEN** two rows across the UBS and USF datasets share the same valid (non-empty, non-placeholder) CNES identifier
- **THEN** dataset preparation retains only the first entry and skips the duplicate regardless of coordinate or name formatting differences

#### Scenario: Cross-dataset duplicate sharing normalized name and bairro
- **WHEN** two rows lack matching `US <number>` and valid CNES identifiers but share the same normalized unit name (accent-stripped, case-folded, with unit-type prefixes stripped) and normalized `bairro`
- **THEN** dataset preparation retains only the first entry and skips the duplicate

#### Scenario: Distinct nearby facilities are not falsely merged
- **WHEN** two distinct physical health units are located within ~50 m of each other but have different `US <number>` codes, different valid CNES identifiers, different normalized names, and distinct rounded coordinates
- **THEN** dataset preparation preserves both units as separate customer nodes

#### Scenario: Placeholder or missing CNES still yields unique node IDs
- **WHEN** multiple distinct selected health units have missing or placeholder CNES values (such as `"9999999"` or `"0000000"`)
- **THEN** dataset preparation does not deduplicate them solely on the placeholder CNES and assigns each selected node a deterministic, unique `id`

#### Scenario: Offline loader rejects duplicate node IDs
- **WHEN** the offline Recife/PE loader reads a `recife_ubs.json` file in which two or more nodes share the same `id`
- **THEN** loading fails with a descriptive `ValueError` rather than silently constructing a CVRP instance with duplicate facility identifiers

#### Scenario: Versioned Recife-UBS-40 static dataset integrity
- **WHEN** the versioned `data/recife_ubs/recife_ubs.json` dataset is inspected or loaded offline
- **THEN** it contains 41 nodes (1 depot + 40 distinct customer health units), all 41 node `id` values are unique, no canonical `US <number>` code appears more than once, and its certified `optimal_value` and `exact_solution` correspond to the deduplicated road distance matrix
