# memetic-cvrp-solver Specification

## Purpose

Provides the optimization algorithms to solve normalized CVRP instances, including a greedy baseline, a Pure Genetic Algorithm, and a Memetic Genetic Algorithm with intra-route local search, guaranteeing feasible solutions by construction.

## Requirements

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
The system SHALL run a permutation-population-based Genetic Algorithm with random seed control, isolated RNG state, tournament selection, elitism, selectable crossover (`OX` or `PMX`), selectable mutation (`Swap` or `Inversion`), and recording of the best distance history per generation.

#### Scenario: Reproducibility by random seed
- **WHEN** the Genetic Algorithm is executed twice with the same instance, same hyperparameters, and same random seed
- **THEN** both runs produce the exact same final solution, same total distance, and same convergence history

#### Scenario: Isolated RNG state across solver invocations
- **WHEN** a caller seeds Python's global `random` module, runs the Genetic Algorithm with a configured seed, and subsequently draws values from Python's global `random` module
- **THEN** the caller's `random` stream matches the sequence produced without invoking the Genetic Algorithm

#### Scenario: Crossover and mutation operator selection
- **WHEN** the user configures crossover (`OX` or `PMX`) and mutation (`Swap` or `Inversion`), including on instances with any valid depot index
- **THEN** all individuals generated across generations remain valid permutations of the instance's customers without duplicated, missing, or depot nodes

### Requirement: Memetic Genetic Algorithm with 2-opt local search
The system SHALL offer a Memetic mode that applies intra-route `2-opt` local search over decoded routes, re-evaluating the concatenated customer permutation under the greedy capacity-split decoder before committing a Lamarckian write-back so that the chromosome is replaced only when the re-decoded total distance strictly improves (by more than `1e-12`) without violating capacity, and the reported distance, individual fitness, per-generation best-distance history, and final decoded routes remain mutually consistent.

#### Scenario: Intra-route improvement or preservation by 2-opt
- **WHEN** `2-opt` local search is applied to a feasible solution
- **THEN** the resulting total distance is less than or equal to the distance before local search and no route violates capacity `Q`

#### Scenario: Lamarckian write-back consistency under greedy capacity-split boundary shifts
- **WHEN** Lamarckian `2-opt` local search is applied to a multi-route Giant Tour permutation whose `2-opt`-improved routes would shift greedy capacity-split boundaries upon concatenation
- **THEN** the returned distance equals the exact greedy-split decoded distance of the returned permutation, is less than or equal to the original permutation's decoded distance, and the candidate permutation is committed only when its re-decoded distance strictly improves over the original distance by more than `1e-12`

#### Scenario: Memetic GA fitness, history, and elitist monotonicity consistency
- **WHEN** the Memetic Genetic Algorithm runs on a valid symmetric or asymmetric instance with elitism enabled (`elite_size >= 1`)
- **THEN** the recorded per-generation best-distance history is monotonically non-increasing across all generations and the final returned solution distance matches both the decoded distance of the returned routes and the final entry of the convergence history within floating-point tolerance (`1e-12`)
