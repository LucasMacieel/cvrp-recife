# Spec Delta

## MODIFIED Requirements

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
