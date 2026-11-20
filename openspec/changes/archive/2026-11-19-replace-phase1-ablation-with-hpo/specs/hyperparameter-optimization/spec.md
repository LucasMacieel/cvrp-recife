# Spec Delta

## MODIFIED Requirements

### Requirement: Multi-instance and multi-seed objective evaluation
The system SHALL evaluate each candidate hyperparameter configuration across a configurable list of CVRP tuning instances — defaulting to the three-instance CVRPLIB training set (`A-n32-k5`, `A-n45-k6`, `A-n60-k9`), excluding `A-n80-k10` and strictly holding out `Recife-UBS-40-road` from default Phase 1 tuning — and multiple deterministic random seeds (`1..N`), minimizing the mean normalized objective across all `(instance, seed)` evaluations.

#### Scenario: Default CVRPLIB training set resolution
- **WHEN** the standalone HPO CLI or runner Phase 1 HPO is invoked without explicit `--instances`
- **THEN** the system resolves the default training set to `A-n32-k5`, `A-n45-k6`, and `A-n60-k9`, excluding `A-n80-k10` and `Recife-UBS-40-road` so the real-world Recife scenario remains strictly unseen during Phase 1 tuning

#### Scenario: Objective aggregation on instances with known optima
- **WHEN** a trial is evaluated on instances that define positive known optimal values
- **THEN** the trial objective equals the mean percentage gap `((distance - optimal_value) / optimal_value) * 100` across all evaluated instances and seeds

#### Scenario: Objective aggregation when an instance lacks a known optimum
- **WHEN** a trial is evaluated on an instance whose `optimal_value` is `None`
- **THEN** the system normalizes the instance's obtained distance against a deterministic reference (such as the Greedy baseline distance for that instance) so instances of different scales contribute comparably to the trial objective
