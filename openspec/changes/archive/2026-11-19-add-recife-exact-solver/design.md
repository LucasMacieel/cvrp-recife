# Design

## Context

See `proposal.md` for motivation. Key codebase and instance constraints that shape this design:

- `Recife-UBS-40-road` has $N = 41$ nodes ($1$ depot + $40$ health units), vehicle capacity $Q = 100$, and total demand $\sum d_i = 700$, giving a tight theoretical minimum fleet lower bound of $K_{\min} = \lceil 700 / 100 \rceil = 7$ (zero slack at $K = 7$; existing Greedy, Pure GA, and Memetic GA runs all use $K = 8$, with Memetic GA best distance `178.3972 km`).
- `distance_matrix_road.npy` is **asymmetric** (`max |d_ij - d_ji| = 3.9108 km`), has `453` directed triangle-inequality violations (up to `3.1786 km`, from OSRM road snapping/one-way routing), and has exact precision at $10^{-4}$ km ($0.1$ m).
- `src/solver/decoder.py` (`validate_routes`) enforces elementary routes (each customer visited once), route load $\le Q$, and **unconstrained** fleet size $K$.
- `CVRPInstance` (`src/data/models.py`), `runner.py`, `stats.py`, `progress.py`, and `plots.py` already consume `instance.optimal_value` whenever present; only `src/data/recife_loader.py` omits loading it from `data/recife_ubs/recife_ubs.json`.
- Because this is a Computational Intelligence academic project, the main Phase 1/Phase 2 benchmark pipeline (`src/experiments/runner.py`) must remain focused on evolutionary/memetic methods and free of compiled OR-solver runtime dependencies.

## Goals / Non-Goals

**Goals:**
- Compute a mathematically proven global optimum (`0.00%` gap) for `Recife-UBS-40-road` under the exact same feasibility rules as the existing CVRP solvers (directed asymmetric distances, capacity `Q = 100`, unconstrained fleet size $K$).
- Provide a single, self-contained, reproducible offline CLI script (`scripts/solve_recife_exact.py`) isolated behind an optional `uv` dependency group (`exact`).
- Independently verify both solver correctness (via `A-n32-k5 == 784.0`) and solution validity (`validate_routes()` + `total_distance()`).
- Persist the proven optimum and full audit certificate into `data/recife_ubs/recife_ubs.json`, load `optimal_value` in `load_recife()`, and refresh `results/` Phase 2 tables and plots with the resulting Recife optimality gap.

**Non-Goals:**
- Integrating the exact solver into `src/experiments/runner.py` as a Phase 2 method or running exact solves on CVRPLIB instances during regular experiments.
- Modifying the Memetic GA, Pure GA, Greedy baseline, or HPO search space/configs.
- Adding exact-vs-GA route overlays to `recife_map.html` (deferred unless requested later).

## Decisions

### 1. Exact Solver Choice: Google OR-Tools CP-SAT (`AddMultipleCircuit`)
- **Decision**: Use `ortools` (`>=9.11`, Google OR-Tools CP-SAT with `AddMultipleCircuit` and exact cumulative load propagation) as the exact solver in `scripts/solve_recife_exact.py`.
- **Rationale**: `AddMultipleCircuit` enforces depot-rooted elementary multi-vehicle routes natively in C++ with zero custom subtour/RCC callback boilerplate (~55 lines vs ~330 lines for a SCIP `Conshdlr`). On this 12-core host, CP-SAT proves `0.00%` global optimality on `A-n32-k5` (`784.0`) in ~8s and on `Recife-UBS-40-road` (`171.9398 km`) in ~29s — ~3× faster than single-threaded `PySCIPOpt` + RCC (~86.5s) while shipping clean Apache-2.0 `manylinux` wheels.
- **Alternatives considered**:
  - `PySCIPOpt` (SCIP Branch-and-Cut + custom `_RCCConshdlr`): Also proved `171.9398 km` (independently confirming the exact optimum), but required ~215 lines of low-level `Conshdlr` callback boilerplate and took ~86.5s.
  - `VRPSolverEasy` (`>=0.1.4`): Initially considered as a BCP solver, but avoided for Python 3.12 / native wheel portability.
  - `scipy.optimize.milp` (HiGHS, compact 2-Commodity Flow): Tested head-to-head; lacks lazy subtour/capacity cut callbacks and timed out with a 4.8% gap on `A-n32-k5` (60s) and a 5.9% gap on `Recife-UBS-40-road` (120s).
  - OR-Tools Routing Library (`RoutingModel`) / `PyVRP` / `HGS-CVRP`: Metaheuristics, not exact solvers — cannot prove optimality or produce a dual lower bound.

### 2. ACVRP Modeling Details (Exact Match to `CVRPInstance` & `decoder.py`)
- **Decision**: Build a directed CP-SAT model on nodes `0..N-1` (remapping `depot` to `0` for `AddMultipleCircuit`) with binary arc variables $x_{ij} \in \{0, 1\}$ ($i \neq j$, pruning infeasible pairs with $d_i + d_j > Q$), exact power-of-10 integer distance scaling (`1` for CVRPLIB integers, `10_000` for Recife $10^{-4}$ km precision), `model.AddMultipleCircuit(circuit_arcs)`, exact cumulative load equality propagation (`load[j] == d[j]` on depot arcs and `load[j] == load[i] + d[j]` on customer arcs via `OnlyEnforceIf(x[i, j])`), minimum fleet bound $\sum_j x_{0j} \ge \lceil \sum d_c / Q \rceil$, and upfront 2-node subtour cuts $x_{ij} + x_{ji} \le 1$.
- **Rationale**:
  - Leaving the depot out-degree unbounded from above ($\ge K_{\min}$ only) guarantees unconstrained fleet size matching `validate_routes()`, avoiding any artificial restriction to $K = 7$ (which has zero slack and may be suboptimal or infeasible) or $K = 8$.
  - Using directed arcs $x_{ij}$ preserves `Recife-UBS-40-road`'s exact asymmetry (and works transparently on symmetric CVRPLIB instances such as `A-n32-k5` for the self-check).
  - Elementary routes in `AddMultipleCircuit` visit every customer exactly once, so the `453` OSRM triangle-inequality violations do not invalidate optimality or feasibility.
  - Avoid setting a tight primal cutoff equal to Memetic GA's `178.3972` by default; if an upper-bound cutoff option (`--upper-bound`) is exposed on the CLI, apply a small safety margin (`+ 1e-2`) so an already-optimal incumbent is never pruned.

### 3. Dependency Isolation via `[dependency-groups]` `exact`
- **Decision**: Declare `exact = ["ortools>=9.11"]` under `[dependency-groups]` in `pyproject.toml` and lock it in `uv.lock`.
- **Rationale**: Keeps `dependencies` (and `uv sync --no-dev` / `uv sync --frozen`) strictly lightweight and portable across platforms, while preserving single-source `pyproject.toml` + `uv.lock` reproducibility via `uv run --group exact scripts/solve_recife_exact.py`.

### 4. Certificate Persistence & Stale-Data Protection
- **Decision**: Persist `optimal_value` (top-level float, rounded only at full precision matching the verified `total_distance`) and an `exact_solution` object directly in `data/recife_ubs/recife_ubs.json`, including `distance_matrix_sha256` computed from `distance_matrix_road.npy`. Update `src/data/recife_loader.py` to pass `optimal_value = payload.get("optimal_value")` (converted to `float` when not `None`) into `CVRPInstance`.
- **Rationale**: Mirrors CVRPLIB `.vrp` files where the published optimum lives alongside the instance definition. If `scripts/prepare_recife_data.py` ever regenerates `recife_ubs.json` from fresh open-data or OSRM inputs, the stale `optimal_value` is automatically cleared rather than silently reused on a changed matrix. Only write `optimal_value` when the solver certifies optimality (`status == "optimal"` and dual/primal gap is `0.0` within tolerance) and independent route verification passes.

### 5. Results Refresh Strategy
- **Decision**: After certifying and saving `optimal_value` into `data/recife_ubs/recife_ubs.json`, re-run Phase 2 via `uv run -m src.experiments.runner --tuned-config results/hpo_best_configs.json` (deterministic seeds `1..30`, `150` generations) to regenerate `results/phase2_*.csv`, `results/phase2_histories.json`, `results/best_solutions.json`, and plots (`boxplot_Recife-UBS-40-road.png`, etc.).
- **Rationale**: Uses the exact existing reproducible entrypoint rather than hand-patching CSVs or PNGs, guaranteeing full consistency across every file in `results/`.

## Risks / Trade-offs

- **[Risk] Integer scaling precision in CP-SAT for arbitrary floating-point distance matrices** → **Mitigation**: Dynamically select the smallest exact power-of-10 scale factor up to $10^6$ (`1` for CVRPLIB, `10_000` for Recife's $0.1$ m road distances) and independently verify `abs(recomputed_distance - solver_objective) <= 1e-4` against `total_distance()`.
- **[Risk] Larger future instances ($n \gg 40$) may take longer to close the dual gap in CP-SAT without Rounded Capacity Cuts** → **Mitigation**: Support configurable `--time-limit` (default `1800` s) and optional `--upper-bound` CLI flags; if a run hits the time limit, print the `[LB, UB]` bracket and exit non-zero without writing `optimal_value`.
- **[Risk] Floating-point discrepancy between solver objective and `total_distance()`** → **Mitigation**: Verify `abs(recomputed_distance - solver_objective) <= 1e-4` and store the exact recomputed `total_distance(routes, dist_matrix, depot)` as `optimal_value` (with `validate_routes()` passing).
- **[Risk] `prepare_recife_data.py` regeneration clears `optimal_value`** → **Mitigation**: Intentional safety feature; document in `README.md` / CLI help that `scripts/solve_recife_exact.py` should be re-run if the Recife dataset or road matrix is regenerated.
