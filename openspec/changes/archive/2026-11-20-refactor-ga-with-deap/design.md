# Design

## Context

See `proposal.md` for motivation. Currently, `src/solver/genetic.py` and `src/solver/operators.py` implement the entire evolutionary loop and operators manually on 2D NumPy arrays (`population`, `fitnesses`, `tournament_selection`, `select_elites`, `crossover_ox`, `crossover_pmx`, `mutate_swap`, `mutate_inversion`). Downstream callers (`src/experiments/hpo.py`, `src/experiments/runner.py`, and the test suite) depend on:

- `GAConfig` and `solve_genetic(instance, config) -> SolverResult` in `src/solver/genetic.py`
- `CROSSOVER_OPERATORS` (`"OX"`, `"PMX"`) and `MUTATION_OPERATORS` (`"Swap"`, `"Inversion"`) in `src/solver/operators.py`
- `decode_giant_tour` and `evaluate_giant_tour` in `src/solver/decoder.py`
- `lamarckian_two_opt` in `src/solver/local_search.py`

## Goals / Non-Goals

**Goals:**
- Delegate GA boilerplate (fitness/individual types, population creation, tournament selection, elitism, `OX`/`PMX` crossover, generational mating/mutation variation, and per-generation minimum-distance logging) to DEAP (`deap.creator`, `deap.base.Toolbox`, `deap.tools`, `deap.algorithms`).
- Preserve 100% compatibility with `GAConfig`, `SolverResult`, `CROSSOVER_OPERATORS` / `MUTATION_OPERATORS` keys, `hpo.py`, and `runner.py`.
- Support arbitrary `CVRPInstance.depot` indices safely with DEAP's 0-indexed permutation crossovers.
- Guarantee deterministic same-seed reproducibility while isolating Python's global `random` state from callers.

**Non-Goals:**
- Replacing CVRP domain logic (`decode_giant_tour`, `evaluate_giant_tour`, `lamarckian_two_opt`, or `solve_greedy`).
- Changing the Optuna HPO search space, CLI flags, or result CSV/JSON schemas.
- Preserving bit-for-bit identical trajectories between the old NumPy-RNG solver and the new DEAP-backed solver for the same numeric seed.

## Decisions

### 1. Chromosome Encoding: 0-Based Customer Index Permutations
- **Decision**: Represent each DEAP `Individual` as a Python `list[int]` containing a permutation of `0..n_cust-1`, indexing into `customers = np.asarray(instance.customers, dtype=np.int64)`. Convert to customer IDs via `customers[ind]` when calling `evaluate_giant_tour`, `decode_giant_tour`, and `lamarckian_two_opt` (and map improved permutations back to index space via a precomputed `cust_to_idx` lookup).
- **Rationale**: `deap.tools.cxOrdered` and `deap.tools.cxPartialyMatched` internally allocate lookup tables of length `len(ind)` indexed directly by gene values (`0..n-1`). Passing raw customer IDs (e.g., `1..n` when `depot == 0`, or non-contiguous IDs when `depot > 0`) raises `IndexError` in DEAP. Index-space encoding lets DEAP's native `cxOrdered` and `cxPartialyMatched` run unmodified for any `depot` index, and handles `n_cust < 2` cleanly via a small length guard.
- **Alternatives considered**:
  - *Wrapping `cxOrdered`/`cxPartialyMatched` to remap customer IDs on every crossover call*: Adds redundant per-mating remapping overhead and duplicates mapping logic.
  - *Assuming `depot == 0` and subtracting 1*: Fragile; breaks `CVRPInstance` when `depot != 0`.

### 2. DEAP `creator` Type Registration
- **Decision**: Register `FitnessMin` (`base.Fitness`, `weights=(-1.0,)`) and `Individual` (`list`, `fitness=creator.FitnessMin`) idempotently at module level in `src/solver/genetic.py` using `if not hasattr(creator, ...)` guards.
- **Rationale**: Calling `creator.create` unconditionally on re-import or repeated `solve_genetic` calls emits DEAP `RuntimeWarning`s about overwriting existing classes. Guarded module-level registration is DEAP's standard pattern and avoids warning noise in tests and HPO loops.

### 3. Evolutionary Loop: `Toolbox` + `varAnd` + Explicit Elitism & Memetic Hook
- **Decision**: Build a per-call `deap.base.Toolbox` registering `indices`, `individual`, `population`, `evaluate`, `mate`, `mutate`, and `select` (`tools.selTournament`, `tournsize=min(max(1, cfg.tournament_k), cfg.pop_size)`). Use `tools.selBest` for elitism, `algorithms.varAnd` for crossover/mutation of the non-elite offspring slice (`pop_size - elite_size`), `tools.HallOfFame(1)` for tracking the global best individual, and `tools.Statistics` + `tools.Logbook` to record generation-0 through generation-`cfg.generations` minimum distances into `SolverResult.history`.
- **Rationale**: `deap.algorithms.eaSimple` does not support elitism (`elite_size`) or memetic per-offspring / per-generation-best Lamarckian `2-opt` local search without reimplementing its loop anyway. Composing `Toolbox`, `varAnd`, `selTournament`, `selBest`, `HallOfFame`, and `Statistics`/`Logbook` removes all manual selection/crossover/mutation/logging boilerplate while keeping exact control over `elite_size`, `local_search_rate`, and `local_search_max_passes`.
- **Alternatives considered**:
  - *`deap.algorithms.eaSimple` with `halloffame`*: Cannot preserve `elite_size` elites in the active population or apply `lamarckian_two_opt` selectively to offspring with probability `local_search_rate` and to the generation best.
  - *`deap.algorithms.eaMuPlusLambda`*: Changes the evolutionary selection semantics from generational elitism to $(\mu + \lambda)$ truncation selection.

### 4. Operators Module (`src/solver/operators.py`)
- **Decision**:
  - Back `CROSSOVER_OPERATORS` (`"OX"`, `"PMX"`) with thin DEAP-compatible wrappers around `deap.tools.cxOrdered` and `deap.tools.cxPartialyMatched` (handling `len(ind) < 2` safely and mutating in-place returning `(ind1, ind2)` per DEAP's convention).
  - Keep `MUTATION_OPERATORS` (`"Swap"`, `"Inversion"`) as thin DEAP-compatible in-place mutation functions returning `(ind,)` using Python's `random` module so they plug directly into `toolbox.register("mutate", ...)` and `algorithms.varAnd`.
  - Remove the hand-rolled `tournament_selection` and `select_elites` functions, which are now superseded by `deap.tools.selTournament` and `deap.tools.selBest`.
- **Rationale**: DEAP provides `cxOrdered` and `cxPartialyMatched`, but does not provide 2-position Swap or contiguous-subsequence Inversion mutations (`deap.tools.mutShuffleIndexes` shuffles each gene independently with probability `indpb`, which is a different operator). Keeping `CROSSOVER_OPERATORS` and `MUTATION_OPERATORS` with the same keys (`"OX"`, `"PMX"`, `"Swap"`, `"Inversion"`) ensures `src/experiments/hpo.py` and `src/solver/genetic.py` work with zero search-space changes.

### 5. RNG Seeding and Global State Isolation
- **Decision**: Wrap the body of `solve_genetic` in a `try ... finally` block (or helper context manager) that saves `random.getstate()`, calls `random.seed(cfg.seed)`, executes the DEAP pipeline, and restores the saved `random` state in `finally`.
- **Rationale**: DEAP's `tools` and `algorithms` draw exclusively from Python's module-level `random` singleton. Saving and restoring state ensures deterministic reproducibility for a given `cfg.seed` while preventing `solve_genetic` from corrupting the caller's `random` stream (important for tests and multi-trial HPO runs).

### 6. Handling `elite_size` Edge Cases and Monotonic Convergence History
- **Decision**: Clamp effective elitism to `n_elites = min(max(0, cfg.elite_size), cfg.pop_size)`. Clone elites (`list(map(toolbox.clone, tools.selBest(population, n_elites)))`) before selecting and varying `n_offspring = cfg.pop_size - n_elites` individuals via `selTournament` + `varAnd`. When `n_offspring` is odd and `varAnd` pairs `offspring[1::2]` with `offspring[::2]`, `varAnd` naturally leaves the last unpaired individual eligible for mutation only, matching standard DEAP behavior and keeping population size exact (`len(elites) + len(offspring) == cfg.pop_size`).
- **Rationale**: Guarantees `len(population) == cfg.pop_size` for all valid `elite_size` values (including `0`, odd `pop_size - elite_size`, or `elite_size >= pop_size`), and preserves monotonically non-increasing `history` whenever `elite_size >= 1`.

## Risks / Trade-offs

- **[Trajectory change for existing seeds]** Switching from `numpy.random.Generator` to DEAP's stdlib `random` changes the exact numeric solutions produced for a given seed compared to pre-DEAP runs → Mitigation: Document this in the proposal/change summary; verify via `tests/test_solver.py` and `tests/test_hpo.py` that same-seed reproducibility, convergence monotonicity, route validity, and HPO end-to-end flows all pass.
- **[DEAP global `random` thread-safety]** Saving/restoring global `random` state is safe for sequential execution (current runner and HPO are single-process sequential), though not thread-safe under concurrent threads → Mitigation: Current codebase runs sequentially; note this constraint if parallel threading is ever introduced (multiprocessing would naturally isolate `random` per process).
- **[Minor overhead from Python `list` ↔ `np.ndarray` conversion in `lamarckian_two_opt`]** `evaluate_giant_tour` already iterates over any `Sequence[int]`, so evaluation works directly without conversion if we map through `customers` or a small list comprehension; `lamarckian_two_opt` only runs on `local_search_rate` fraction of offspring and the generation best → Mitigation: Keep `customers` as a Python `list[int]` (or tuple) for fast O(1) Python indexing `[customers[i] for i in ind]` to avoid NumPy scalar boxing overhead in hot loops.
