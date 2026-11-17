# Spec Delta

## Purpose

Provides the optimization algorithms to solve normalized CVRP instances, including a greedy baseline, a Pure Genetic Algorithm, and a Memetic Genetic Algorithm with intra-route local search, guaranteeing feasible solutions by construction.

## ADDED Requirements

### Requirement: Feasible decoding by construction
The system SHALL decode any complete customer permutation (Giant Tour) into a set of routes starting and ending at the depot through sequential partitioning that never exceeds vehicle capacity `Q`.

#### Scenario: Capacity-respecting partitioning
- **WHEN** a customer permutation is decoded with capacity `Q` and known demands
- **THEN** every generated route has a sum of demands less than or equal to `Q`, each customer is served exactly once, and the total distance equals the exact sum of route distances

### Requirement: Deterministic greedy heuristic baseline
The system SHALL provide a baseline solver based on Nearest Neighbor that opens a new route whenever the next nearest customer exceeds the remaining vehicle capacity.

#### Scenario: Baseline solution construction
- **WHEN** the greedy baseline is executed on a valid instance
- **THEN** the system returns a complete set of feasible routes, its total distance, and execution runtime

### Requirement: Configurable Genetic Algorithm for permutations
The system SHALL run a permutation-population-based Genetic Algorithm with random seed control, tournament selection, elitism, selectable crossover (`OX` or `PMX`), selectable mutation (`Swap` or `Inversion`), and recording of the best distance history per generation.

#### Scenario: Reproducibility by random seed
- **WHEN** the Genetic Algorithm is executed twice with the same instance, same hyperparameters, and same random seed
- **THEN** both runs produce the exact same final solution, same total distance, and same convergence history

#### Scenario: Crossover and mutation operator selection
- **WHEN** the user configures crossover (`OX` or `PMX`) and mutation (`Swap` or `Inversion`)
- **THEN** all individuals generated across generations remain valid permutations without duplicated or missing customers

### Requirement: Memetic Genetic Algorithm with 2-opt local search
The system SHALL offer a Memetic mode that applies intra-route `2-opt` local search over decoded routes, replacing the customer order in the permutation only when there is a strict distance improvement without violating capacity.

#### Scenario: Intra-route improvement or preservation by 2-opt
- **WHEN** `2-opt` local search is applied to a feasible solution
- **THEN** the resulting total distance is less than or equal to the distance before local search and no route violates capacity `Q`
