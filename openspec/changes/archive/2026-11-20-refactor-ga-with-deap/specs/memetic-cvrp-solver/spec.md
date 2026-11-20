# Spec Delta

## MODIFIED Requirements

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
