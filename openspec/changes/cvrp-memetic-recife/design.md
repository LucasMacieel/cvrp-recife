# Design

## Context

This project starts from an empty repository (see `proposal.md` for motivation and capability scope). The architectural goal is to keep the evolutionary core completely decoupled from the data source (CVRPLIB `EUC_2D` instances vs. geographic coordinates of UBSs/Polyclinics in Recife/PE), enabling a team of up to 3 members to develop and test the data, optimization, and experimentation modules in parallel.

```text
+-------------------------------------------------------------------------+
|                      PROPOSED MODULAR ARCHITECTURE                      |
+-------------------------------------------------------------------------+
|                                                                         |
|  data/                                                                  |
|   |-- cvrplib/          (.vrp files + known optima)                     |
|   '-- recife_ubs/       (recife_ubs.json + distance_matrix_road.npy)    |
|           |                                                             |
|           v                                                             |
|  src/data/              (parsers -> unified CVRPInstance)               |
|           |                                                             |
|           v                                                             |
|  src/solver/            (greedy.py, operators.py, local_search.py,      |
|           |              genetic.py)                                    |
|           v                                                             |
|  src/experiments/       (runner.py, stats.py, plots.py, map_recife.py)  |
|           |                                                             |
|           v                                                             |
|  results/               (raw CSVs, summaries, PNGs, recife_map.html)    |
+-------------------------------------------------------------------------+
```

## Goals / Non-Goals

**Goals:**
- Unify CVRPLIB and Recife/PE instances under a single `CVRPInstance` structure (matrix `D[N, N]`, demands `demands[N]`, capacity `Q`, depot index, and optional metadata such as known optimum and lat/lon).
- Implement all evolutionary operators and local search from scratch in Python 3.10+ and NumPy, without black-box GA frameworks.
- Guarantee deterministic execution via `numpy.random.Generator` (explicit seeds) and 100% offline operation during experiments using the pre-processed Recife dataset.
- Produce statistically comparable results (30 seeds per main configuration) and artifacts ready for analysis in the course report.

**Non-Goals:**
- Do not model time windows (VRPTW), heterogeneous fleets, or real-time dynamic traffic constraints.
- Do not build a web interface or production API; execution is via CLI/Python scripts and static charts + Folium HTML.
- Do not use commercial exact solvers or additional metaheuristics outside the scope (Greedy Baseline, Pure GA, and Memetic GA with `2-opt`), except for occasional spot checks.

## Decisions

### 1. Unified Abstraction via Pre-computed Distance Matrix (`CVRPInstance`)
- **Decision:** Every loader converts the input instance into an immutable `dataclass` with `distance_matrix: np.ndarray` (`float64`, shape `(N, N)`), `demands: np.ndarray` (`int`, shape `(N,)`), `capacity: int`, `depot: int`, and optional metadata (`coords`, `latlon`, `optimal_value`, `node_names`).
- **Alternatives considered:** Computing distances on-the-fly inside the fitness function; discarded because it would couple the GA to the metric type (`EUC_2D` vs. Haversine vs. road) and make evaluation much slower.
- **Rationale:** Completely separates the domain (Recife or CVRPLIB) from the evolutionary engine and makes route distance calculation an O(N) NumPy indexing operation.

### 2. Giant Tour Encoding with Capacity-Constrained Greedy Split
- **Decision:** Represent each individual as a permutation of size `N - 1` (customers only, excluding depot node `0`). Decoding traverses the permutation accumulating demand up to limit `Q`; when the next customer exceeds `Q`, it closes the current route by returning to the depot and starts a new route.
- **Alternatives considered:**
  - Chromosome with explicit route delimiters (`0`s inserted in the permutation): increases the search space with redundant route permutations and produces infeasible individuals after standard crossover.
  - Capacity penalty as a soft constraint: requires sensitive calibration of penalty coefficients per instance.
- **Rationale:** Giant Tour + greedy Split guarantees 100% feasibility by construction and allows using classic permutation operators (`OX`, `PMX`, `Swap`, `Inversion`) without a repair step. *(Accepted trade-off: an optimal dynamic programming Split by Prins would be stronger, but increases code complexity for the course scope; greedy Split combined with `2-opt` serves with didactic clarity.)*

### 3. Custom Implementation in Python + NumPy vs. DEAP/PyGAD Framework
- **Decision:** Implement tournament selection, elitism, `OX`, `PMX`, `Swap`, `Inversion`, and `2-opt` directly with Python + NumPy.
- **Alternatives considered:** `DEAP` or `PyGAD`.
- **Rationale:** Computational Intelligence courses value explicit mastery of operators; furthermore, coupling intra-route `2-opt` and reconstructing the permutation (Lamarckian learning, writing the improved order back into the chromosome) is more straightforward without framework adapters.

### 4. Recife/PE Scenario with Static Road Matrix (OSRM) + Haversine Fallback
- **Decision:** Provide a one-time preparation script (`scripts/prepare_recife_data.py`) that fetches real coordinates of ~30 to 45 UBSs/Polyclinics (Recife Open Data / Overpass OSM) and the road distance table from the public OSRM server, saving `data/recife_ubs/recife_ubs.json` and `data/recife_ubs/distance_matrix_road.npy` in the repository. During experiments, scripts read only local files, supporting a flag to compare road vs. Haversine matrices.
- **Alternatives considered:** Querying OSRM at runtime (fragile without network / subject to rate limits) or using only Haversine (ignores bridges and barriers of the Capibaribe and Beberibe rivers in Recife).
- **Rationale:** Guaranteed offline reproducibility + urban realism of Recife + opportunity to compare in the report how "straight-line optimal" routes differ from "road-network optimal" routes.

### 5. Lamarckian Application of `2-opt` in the Memetic GA
- **Decision:** In the Memetic GA, after decoding an individual into routes, apply `2-opt` best-improvement (or first-improvement until local convergence) on each sub-route with 4 or more customers, and **update the chromosome permutation** with the concatenation of the optimized routes. Apply `2-opt` to the best individual / top-k of the population or with controlled probability `p_ls` (e.g., `0.2` to `1.0`) to balance computational cost.
- **Alternatives considered:** Applying `2-opt` only during evaluation without altering the genotype (Baldwin effect) or applying it to 100% of the population in all generations without control.
- **Rationale:** Lamarckian updating preserves improved building blocks for subsequent generations and controls CPU time on larger instances (e.g., `A-n80-k10`).

### 6. Two-Phase Experimental Protocol + Statistical Tests
- **Decision:**
  - **Phase 1 (Operator Ablation):** Run 10 seeds on 2 representative CVRPLIB instances comparing the 4 combinations (`OX`/`PMX` x `Swap`/`Inversion`) in the Pure GA to choose the best operator pair with empirical justification.
  - **Phase 2 (Main Comparison):** Run 30 seeds on CVRPLIB instances (`A-n32-k5`, `A-n45-k6`, `A-n60-k9`, `A-n80-k10`) and on the Recife/PE scenario (road and Haversine) comparing: Greedy Baseline, Pure GA, and Memetic GA.
  - **Statistical Analysis:** Use Mann-Whitney U test (or paired Wilcoxon on the same seeds) via `scipy.stats` to verify significance (`p < 0.05`) between Pure GA and Memetic GA.

## Risks / Trade-offs

- **Risk:** High runtime of `2-opt` applied to the entire population on instances with `N >= 80` and 30 seeds. -> **Mitigation:** Configure local search probability `p_ls` (e.g., apply to top-k or `p_ls=0.3`), limit max `2-opt` iterations, or implement O(1) delta evaluation per edge swap instead of recalculating the entire route.
- **Risk:** Public OSRM or Overpass API unavailable when generating the Recife dataset. -> **Mitigation:** Version the pre-processed dataset in `data/recife_ubs/` and keep automatic Haversine generation + local fallback data in case the collection script needs to run offline.
- **Risk:** OSRM road matrix being asymmetric (`D[i][j] != D[j][i]` due to one-way streets in Recife). -> **Mitigation:** Route cost calculation and `2-opt` delta must properly handle potentially asymmetric matrices (recomputing the reversed segment in `2-opt` when `symmetric=False`, instead of assuming zero reversal cost).
