# Tasks

## 1. Environment & Dependency Setup

- [x] 1.1 Add `deap>=1.4` to `[project].dependencies` in `pyproject.toml`, run `uv lock` and `uv sync`, and verify `uv run python -c "import deap; from deap import algorithms, base, creator, tools"` succeeds cleanly.

## 2. DEAP-Backed Evolutionary Operators

- [x] 2.1 Refactor `src/solver/operators.py` to back `CROSSOVER_OPERATORS` (`"OX"`, `"PMX"`) with DEAP's `deap.tools.cxOrdered` and `deap.tools.cxPartialyMatched` (with a `len < 2` guard), keep DEAP-compatible in-place `mutate_swap` and `mutate_inversion` in `MUTATION_OPERATORS` (`"Swap"`, `"Inversion"`) using Python's `random` module, and remove the hand-rolled `tournament_selection` and `select_elites` helpers; verify `CROSSOVER_OPERATORS` and `MUTATION_OPERATORS` expose the exact expected keys and DEAP return signatures.
- [x] 2.2 Update operator unit tests in `tests/test_solver.py` to cover DEAP-backed `OX`/`PMX` crossovers and `Swap`/`Inversion` mutations over 0-based permutations (including `n < 2` edge cases) and verify `uv run pytest tests/test_solver.py -k operators` passes.

## 3. DEAP-Backed Genetic & Memetic Solver

- [x] 3.1 Refactor `src/solver/genetic.py` to use idempotent `deap.creator` (`FitnessMin`, `Individual`) registration, a per-call `deap.base.Toolbox` (`indices`, `individual`, `population`, `evaluate`, `mate`, `mutate`, `select`), `deap.tools.selTournament`, `deap.tools.selBest`, `deap.tools.HallOfFame`, `deap.tools.Statistics`/`Logbook`, and `deap.algorithms.varAnd`, encoding chromosomes as `0..n_cust-1` indices into `instance.customers`, integrating `lamarckian_two_opt` when `cfg.memetic` is enabled, and isolating Python's global `random` state via `random.getstate()`/`random.setstate()` in a `try ... finally` block; verify `solve_genetic` returns a valid `SolverResult` with preserved `GAConfig` compatibility.
- [x] 3.2 Update and expand GA/Memetic tests in `tests/test_solver.py` to verify same-seed reproducibility, monotonic convergence history, global `random` RNG state isolation, arbitrary non-zero `depot` index handling, `elite_size` edge cases (`0` and odd `pop_size - elite_size`), and Memetic `2-opt` execution, and run `uv run pytest tests/test_solver.py` to confirm all pass.
- [x] 3.3 Update `README.md` project structure descriptions for `src/solver/operators.py` and `src/solver/genetic.py` to document DEAP-backed GA primitives and verify the updated descriptions match the implemented modules.

## 4. End-to-End Integration Verification

- [x] 4.1 Run the full test suite (`uv run pytest`) and verify all solver, HPO (`tests/test_hpo.py`), experiment (`tests/test_experiments.py`), data-loading, and exact-solver tests pass with zero warnings from DEAP `creator` re-registration.
- [x] 4.2 Verify `uv sync --frozen --no-dev` and `uv run -m src.experiments.runner --help` / `uv run -m src.experiments.hpo --help` succeed cleanly against the updated `uv.lock`.
