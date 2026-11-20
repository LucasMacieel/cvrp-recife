# Memetic CVRP — CVRPLIB Benchmarks & Supply Distribution Across UBS/USF Health Units in Recife/PE

Computational Intelligence course project applying **Evolutionary Computation** (Pure Genetic Algorithm and Memetic Genetic Algorithm with intra-route `2-opt` local search) to the **Capacitated Vehicle Routing Problem (CVRP)**, tuned via Bayesian Hyperparameter Optimization (Optuna TPE) on classical CVRPLIB benchmarks and evaluated on a held-out real-world geographic scenario for distributing medical supplies to Primary Health Units (UBSs/USFs) in Recife/PE.

## Project Structure

```text
cvrp-recife/
├── data/
│   ├── cvrplib/          # Classical instances (.vrp): A-n32-k5, A-n45-k6, A-n60-k9
│   └── recife_ubs/       # Static dataset of 40 UBSs/USFs + depot (JSON + road distance matrix .npy)
├── scripts/
│   ├── prepare_recife_data.py  # Consolidation of Recife Open Data + OSRM road matrix
│   └── solve_recife_exact.py   # Offline exact ACVRP solver (OR-Tools CP-SAT, optional `exact` group)
├── src/
│   ├── data/
│   │   ├── models.py           # CVRPInstance dataclass and integrity validations
│   │   ├── cvrplib_loader.py   # EUC_2D parser for CVRPLIB .vrp files
│   │   └── recife_loader.py    # Offline loader for Recife OSRM road-network instance
│   ├── solver/
│   │   ├── decoder.py          # Giant Tour decoder with greedy capacity-constrained Split
│   │   ├── greedy.py           # Deterministic baseline (capacitated Nearest Neighbor)
│   │   ├── operators.py        # Tournament, elitism, OX/PMX crossovers, and Swap/Inversion mutations
│   │   ├── local_search.py     # Intra-route 2-opt local search (symmetric and asymmetric)
│   │   └── genetic.py          # Pure GA and Lamarckian Memetic GA
│   └── experiments/
│       ├── runner.py           # Runner for Phase 1 (Bayesian HPO) -> Phase 2 (30-seed benchmarking)
│       ├── hpo.py              # Standalone Optuna TPE hyperparameter optimization for Pure GA and Memetic GA
│       ├── progress.py         # Rich progress bars and summary tables for experiments and HPO
│       ├── stats.py            # Aggregation, gap %, and Wilcoxon / Mann-Whitney tests
│       ├── plots.py            # Convergence curves, comparative boxplots, and best-solution route plots (.png)
│       └── map_recife.py       # Interactive Folium map of routes in Recife (.html)
├── tests/                      # Unit tests and smoke tests suite (pytest)
└── results/                    # HPO configs/trials, Phase 2 CSVs, PNG charts, and recife_map.html
```

## Installation

Requires Python 3.10+ and [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync
```

## Input Format & Preprocessing

Both data sources are normalized into an immutable, validated [`CVRPInstance`](src/data/models.py) before entering the solver pipeline (`distance_matrix` of shape `(N, N)` with finite non-negative `float64` values, `demands` of shape `(N,)` with `demands[depot] == 0` and `0 <= demands <= capacity`, positive integer `capacity`, and automatic `is_symmetric` detection for `2-opt`):

- **CVRPLIB (`.vrp`) — [`load_cvrplib`](src/data/cvrplib_loader.py):** Parses TSPLIB `EUC_2D` files (`DIMENSION`, `CAPACITY`, `NODE_COORD_SECTION`, `DEMAND_SECTION`, `DEPOT_SECTION`). 1-based node IDs are sorted and reindexed to `0..N-1`; pairwise Euclidean distances are rounded via `floor(d + 0.5)`; `optimal_value` is extracted from `COMMENT` (`Optimal/Best value`) when present.
- **Recife/PE (`recife_ubs.json` + `distance_matrix_road.npy`) — [`load_recife`](src/data/recife_loader.py):**
  - [`recife_ubs.json`](data/recife_ubs/recife_ubs.json): Stores `capacity` (`100`), `depot` (`0`), `demand_metadata`, and `nodes` (41 entries: index `0` is `DEPOT-CAF` with `demand: 0`; indices `1..40` are UBS/USF units with `lat`, `lon`, and integer `demand` scaled into `[10, 40]` from pharmacy stockout counts).
  - [`distance_matrix_road.npy`](data/recife_ubs/distance_matrix_road.npy): Precomputed `(41, 41)` `float64` OSRM driving-distance matrix in `km` (asymmetric due to one-way urban streets; required by [`load_recife`](src/data/recife_loader.py)).

## Running

### 1. Unit tests and smoke tests

```bash
uv run pytest
```

### 2. Optional Recife/PE dataset preparation (already versioned in `data/recife_ubs/`)

The static dataset consolidates 40 primary care units (**UBS** and **USF** — *Unidades Básicas de Saúde* and *Unidades de Saúde da Família*) from Recife Open Data along with the central depot (`CAF Recife`), estimating unit replenishment demands from municipal pharmacy stockout records (`medicamentos-por-unidade-de-saude.csv`, counting `quantidade = 0` items per unit and min-max scaling into `[10, 40]` for `capacity = 100`).

```bash
uv run scripts/prepare_recife_data.py
```

Optional CLI flags: `--output-dir`, `--d-min`, `--d-max`, `--capacity`, `--stock-csv`. Queries Recife Open Data (unless `--stock-csv` is provided) and the public OSRM API (`router.project-osrm.org`) for driving distances, failing fast with `RuntimeError` if OSRM is unavailable or returns unreachable cells. Note that regenerating `recife_ubs.json` via `prepare_recife_data.py` clears any previously certified `optimal_value` and `exact_solution` metadata so stale optima are never reused on updated road matrices.

### 2b. Optional offline exact optimum certification (Recife/PE)

`Recife-UBS-40-road` ships with a certified `optimal_value` and `exact_solution` provenance record in [`data/recife_ubs/recife_ubs.json`](data/recife_ubs/recife_ubs.json). To reproduce or re-certify the global optimum offline (using Google OR-Tools CP-SAT from the optional `exact` dependency group):

```bash
uv run --group exact scripts/solve_recife_exact.py
```

Optional CLI flags (`uv run --group exact scripts/solve_recife_exact.py --help`): `--data-dir`, `--time-limit`, `--upper-bound`, `--skip-self-check`, `--dry-run`. The script verifies `A-n32-k5 == 784.0` before solving `Recife-UBS-40-road`, validates all routes against `validate_routes()` and `total_distance()`, and records a SHA-256 fingerprint of `distance_matrix_road.npy`.

### 3. Experimental Methodology: Phase 1 (Bayesian HPO) → Phase 2 (Benchmarking & Statistical Evaluation)

The experimental pipeline follows a leakage-free **Phase 1 (Bayesian HPO) → Phase 2 (Benchmarking & Statistical Evaluation)** protocol:

1. **Phase 1 (Bayesian HPO):** Uses Optuna's Tree-structured Parzen Estimator (TPE) to jointly optimize categorical operators (`OX`/`PMX`, `Swap`/`Inversion`) and numeric hyperparameters (`pop_size`, `crossover_rate`, `mutation_rate`, `tournament_k`, `elite_size`, plus `local_search_rate` and `local_search_max_passes` for `Memetic_GA`) independently for `Pure_GA` and `Memetic_GA`.
   - **Training set (`A-n32-k5`, `A-n45-k6`, `A-n60-k9`):** Three symmetric Euclidean CVRPLIB instances spanning 32–60 nodes (bracketing Recife's 41 nodes). Default budget: `--hpo-trials 30`, `--hpo-seeds 3`, `--hpo-generations 100`, `--hpo-seed 42`.
   - **Held-out split & domain shift:** `Recife-UBS-40-road` (41 nodes, asymmetric OSRM road network) is strictly held out from Phase 1 tuning. Evaluating symmetric-tuned configs on the asymmetric urban road network tests out-of-distribution generalization with zero data leakage.
2. **Phase 2 (Benchmarking & Statistical Evaluation):** Runs across all 4 instances (`A-n32-k5`, `A-n45-k6`, `A-n60-k9`, and held-out `Recife-UBS-40-road`), comparing the deterministic `Greedy` baseline (`seed=0`) against the Phase 1 tuned `Pure_GA` and `Memetic_GA` for `--phase2-seeds` runs (default `30`) with `--generations` (default `150`). Statistical comparison (`phase2_stats_tests.csv`) runs two-sided Wilcoxon signed-rank (paired by seed) and Mann-Whitney U tests between `Pure_GA` and `Memetic_GA` (`significant_005` when `wilcoxon_p < 0.05`).
3. **Charts & Map:** Generates convergence curves, comparative boxplots, the static best-solution route plot (`best_solution_Recife-UBS-40-road.png`), and the interactive Folium map (`recife_map.html`) from the best `Memetic_GA` routes on `Recife-UBS-40-road` (querying OSRM for road-snapped polylines with straight-line fallback if offline).

#### Option A: 1-step full pipeline (inline Phase 1 HPO → Phase 2)

```bash
uv run -m src.experiments.runner
```

Optional CLI parameters (`uv run -m src.experiments.runner --help`): `--phase2-seeds` (`30`), `--generations` (`150`), `--hpo-trials` (`30`), `--hpo-seeds` (`3`), `--hpo-generations` (`100`), `--hpo-seed` (`42`), `--tune` (optional alias for inline Phase 1 HPO, mutually exclusive with `--tuned-config`), `--output-dir` (`results`), `--no-progress`.

#### Option B: 2-step pipeline (standalone Phase 1 HPO + Phase 2 with `--tuned-config`)

Run Phase 1 Bayesian HPO standalone (`uv run -m src.experiments.hpo --help`):

```bash
uv run -m src.experiments.hpo --instances A-n32-k5 A-n45-k6 A-n60-k9 --trials 30 --seeds 3 --generations 100
```

This exports `results/hpo_best_configs.json`, `results/hpo_trials_pure_ga.csv`, and `results/hpo_trials_memetic_ga.csv` (use `--method pure|memetic|both`, `--hpo-seed`, `--output-dir`, or `--no-progress`). Then run Phase 2 benchmarking using the saved configs:

```bash
uv run -m src.experiments.runner --tuned-config results/hpo_best_configs.json
```

Results are saved in `results/`:
- `hpo_best_configs.json`, `hpo_trials_pure_ga.csv`, `hpo_trials_memetic_ga.csv`
- `phase2_results.csv`, `phase2_summary.csv`, `phase2_stats_tests.csv`
- `phase2_histories.json`, `best_solutions.json`
- `convergence_*.png`, `boxplot_*.png`, `best_solution_*.png`
- `recife_map.html`

## Output Format & Node Index Mapping (`best_solutions.json`)

[`results/best_solutions.json`](results/best_solutions.json) stores the best route plans per instance and solver (`Greedy`, `Pure_GA`, `Memetic_GA`):

- **Best-of-seeds selection:** For `Pure_GA` and `Memetic_GA`, the saved entry is the single run with the lowest `distance` across all Phase 2 seeds (not an average).
- **Route representation (`routes`):** A `list[list[int]]` where each inner list is one vehicle's ordered sequence of customer visits (`len(routes) == num_vehicles`).
- **Implicit depot (`0`):** The depot index (`0`) is omitted from every inner list; each route implicitly starts and ends at the depot (`0 -> r[0] -> ... -> r[-1] -> 0`).
- **0-based node index mapping:**
  - **Recife (`Recife-UBS-40-road`):** Indices `0..40` match the 0-based array position in `"nodes"` inside [`data/recife_ubs/recife_ubs.json`](data/recife_ubs/recife_ubs.json) (`0` is `DEPOT-CAF`; `1..40` are the 40 UBS/USF units).
  - **CVRPLIB (`A-n32-k5`, `A-n45-k6`, `A-n60-k9`):** `.vrp` files use 1-based IDs in `NODE_COORD_SECTION`; [`load_cvrplib`](src/data/cvrplib_loader.py) sorts those IDs and reindexes them to 0-based (`idx = node_id - 1`, so `.vrp` node `1` becomes `0`, node `2` becomes `1`, etc.).
- **Distance units & symmetry:** CVRPLIB distances use TSPLIB `EUC_2D` nearest-integer rounding (`floor(d + 0.5)`). Recife distances are in kilometers (`km`), using the precomputed OSRM driving matrix (`Recife-UBS-40-road`, which is asymmetric due to one-way streets).

## Recife Routes Map

Click the map preview below to open the interactive Folium map ([`results/recife_map.html`](results/recife_map.html)) in your browser:

[![Recife UBS/USF Routes Map](results/recife_map_preview.png)](https://lucasmacieel.github.io/cvrp-recife/results/recife_map.html)

> [Open interactive map](https://lucasmacieel.github.io/cvrp-recife/results/recife_map.html) · [View source HTML](results/recife_map.html)
