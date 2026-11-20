# Proposal

## Why

The Genetic Algorithm in `src/solver/genetic.py` and `src/solver/operators.py` currently hand-rolls standard evolutionary computation boilerplate—population/fitness arrays, tournament selection, elitism bookkeeping, Order Crossover (OX), Partially Mapped Crossover (PMX), and generational mating/mutation/logging loops. Replacing this custom boilerplate with the DEAP (`deap`) framework reduces maintenance overhead, leverages battle-tested evolutionary primitives, and keeps the codebase focused on CVRP-specific domain logic (Giant Tour capacity-split decoding, `Swap`/`Inversion` mutations, and Lamarckian intra-route `2-opt` local search).

## What Changes

- Add `deap` as a core runtime dependency in `pyproject.toml` and lock it in `uv.lock`.
- Refactor `src/solver/genetic.py` to use DEAP primitives (`deap.creator`, `deap.base.Toolbox`, `deap.tools.selTournament`, `deap.tools.selBest`, `deap.tools.HallOfFame`, `deap.tools.Statistics`, `deap.tools.Logbook`, and `deap.algorithms.varAnd`) for individual/fitness definition, population initialization, selection, elitism, variation, and per-generation convergence tracking.
- Refactor `src/solver/operators.py` to back `OX` and `PMX` crossovers with `deap.tools.cxOrdered` and `deap.tools.cxPartialyMatched`, retain thin DEAP-compatible `Swap` and `Inversion` mutation operators (which DEAP does not provide natively), and remove the hand-rolled `tournament_selection` and `select_elites` helpers.
- Encode DEAP individuals as `0..n_cust-1` index permutations mapped to `instance.customers` so DEAP's 0-indexed `cxOrdered` and `cxPartialyMatched` work natively for any depot index without index errors.
- Isolate Python's stdlib `random` RNG state around each DEAP `solve_genetic` call so runs remain strictly reproducible by `GAConfig.seed` without mutating caller RNG state (e.g., Optuna or tests).
- Preserve the public `GAConfig` and `solve_genetic(instance, config) -> SolverResult` APIs as well as the `"OX"`, `"PMX"`, `"Swap"`, `"Inversion"` operator registry keys used by `src/experiments/hpo.py` and `src/experiments/runner.py`.
- Update `tests/test_solver.py` and `README.md` to reflect the DEAP-backed GA implementation.

## Capabilities

### New Capabilities

(None)

### Modified Capabilities

- `memetic-cvrp-solver`: Implement the configurable Genetic Algorithm and Memetic GA boilerplate (individual/fitness types, selection, elitism, `OX`/`PMX` crossover, variation, and convergence logging) using the DEAP framework while preserving operator names, seed reproducibility, RNG isolation, and Lamarckian `2-opt` integration.
- `python-environment`: Add `deap` to the required core runtime dependencies declared in `pyproject.toml` and locked in `uv.lock`.

## Impact

- **Dependencies**: Adds `deap` to `pyproject.toml` (`[project].dependencies`) and updates `uv.lock`.
- **Affected code**:
  - `src/solver/operators.py` (DEAP-backed `CROSSOVER_OPERATORS`, DEAP-compatible `MUTATION_OPERATORS`, removal of custom `tournament_selection` and `select_elites`)
  - `src/solver/genetic.py` (DEAP `creator`, `Toolbox`, `varAnd`, `selTournament`, `selBest`/`HallOfFame`, `Statistics`/`Logbook`, RNG state isolation)
  - `tests/test_solver.py` (updated operator/selection tests and added DEAP/RNG-isolation checks)
  - `README.md` (updated project structure description for `operators.py` and `genetic.py`)
- **Downstream callers**: `src/experiments/hpo.py`, `src/experiments/runner.py`, `tests/test_hpo.py`, and `tests/test_experiments.py` require no API changes.
- **Behavioral note**: Because DEAP uses Python's `random` module internally rather than `numpy.random.Generator`, exact numerical trajectories for a given `seed` will differ from pre-DEAP runs, while same-seed reproducibility under DEAP remains deterministic.
