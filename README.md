# Memetic CVRP — CVRPLIB Benchmarks & Supply Distribution Across UBS/USF Health Units in Recife/PE

Computational Intelligence course project applying **Evolutionary Computation** (Pure Genetic Algorithm and Memetic Genetic Algorithm with intra-route `2-opt` local search) to the **Capacitated Vehicle Routing Problem (CVRP)**, validated on classical CVRPLIB benchmark instances and a real-world geographic scenario for distributing medical supplies to Primary Health Units (UBSs/USFs) in Recife/PE.

## Project Structure

```text
cvrp-recife/
├── data/
│   ├── cvrplib/          # Classical instances (.vrp): A-n32-k5, A-n45-k6, A-n60-k9, A-n80-k10
│   └── recife_ubs/       # Static dataset of 40 UBSs/USFs + depot (JSON + road distance matrix .npy)
├── scripts/
│   └── prepare_recife_data.py  # Consolidation of Recife Open Data + OSRM/Haversine matrix
├── src/
│   ├── data/
│   │   ├── models.py           # CVRPInstance dataclass and integrity validations
│   │   ├── cvrplib_loader.py   # EUC_2D parser for CVRPLIB .vrp files
│   │   └── recife_loader.py    # Offline loader for Recife ('road' and 'haversine' modes)
│   ├── solver/
│   │   ├── decoder.py          # Giant Tour decoder with greedy capacity-constrained Split
│   │   ├── greedy.py           # Deterministic baseline (capacitated Nearest Neighbor)
│   │   ├── operators.py        # Tournament, elitism, OX/PMX crossovers, and Swap/Inversion mutations
│   │   ├── local_search.py     # Intra-route 2-opt local search (symmetric and asymmetric)
│   │   └── genetic.py          # Pure GA and Lamarckian Memetic GA
│   └── experiments/
│       ├── runner.py           # Runner for Phase 1 (ablation) and Phase 2 (30-seed comparison)
│       ├── stats.py            # Aggregation, gap %, and Wilcoxon / Mann-Whitney tests
│       ├── plots.py            # Convergence curves and comparative boxplots (.png)
│       └── map_recife.py       # Interactive Folium map of routes in Recife (.html)
├── tests/                      # Unit tests and smoke tests suite (pytest)
└── results/                    # Raw/summary CSVs, PNG charts, and recife_map.html
```

## Installation

Requires Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Input Format & Preprocessing

Both data sources are normalized into an immutable, validated [`CVRPInstance`](src/data/models.py) before entering the solver pipeline (`distance_matrix` of shape `(N, N)` with finite non-negative `float64` values, `demands` of shape `(N,)` with `demands[depot] == 0` and `0 <= demands <= capacity`, positive integer `capacity`, and automatic `is_symmetric` detection for `2-opt`):

- **CVRPLIB (`.vrp`) — [`load_cvrplib`](src/data/cvrplib_loader.py):** Parses TSPLIB `EUC_2D` files (`DIMENSION`, `CAPACITY`, `NODE_COORD_SECTION`, `DEMAND_SECTION`, `DEPOT_SECTION`). 1-based node IDs are sorted and reindexed to `0..N-1`; pairwise Euclidean distances are rounded via `floor(d + 0.5)`; `optimal_value` is extracted from `COMMENT` (`Optimal/Best value`) when present.
- **Recife/PE (`recife_ubs.json` + `distance_matrix_road.npy`) — [`load_recife`](src/data/recife_loader.py):**
  - [`recife_ubs.json`](data/recife_ubs/recife_ubs.json): Stores `capacity` (`100`), `depot` (`0`), `demand_metadata`, and `nodes` (41 entries: index `0` is `DEPOT-CAF` with `demand: 0`; indices `1..40` are UBS/USF units with `lat`, `lon`, and integer `demand` scaled into `[10, 40]` from pharmacy stockout counts).
  - [`distance_matrix_road.npy`](data/recife_ubs/distance_matrix_road.npy): Precomputed `(41, 41)` `float64` driving-distance matrix in `km` used in `road` mode (may be asymmetric; falls back to Haversine if absent). In `haversine` mode, pairwise geodesic distances in `km` are computed directly from `lat`/`lon`.

## Running

### 1. Unit tests and smoke tests

```bash
pytest
```

### 2. Optional Recife/PE dataset preparation (already versioned in `data/recife_ubs/`)

The static dataset consolidates 40 primary care units (**UBS** and **USF** — *Unidades Básicas de Saúde* and *Unidades de Saúde da Família*) from Recife Open Data along with the central depot (`CAF Recife`), estimating unit replenishment demands from municipal pharmacy stockout records (`medicamentos-por-unidade-de-saude.csv`, counting `quantidade = 0` items per unit and min-max scaling into `[10, 40]` for `capacity = 100`).

```bash
python scripts/prepare_recife_data.py
```

Optional CLI flags: `--output-dir`, `--d-min`, `--d-max`, `--capacity`, `--stock-csv`. Queries Recife Open Data (unless `--stock-csv` is provided) and the public OSRM API (`router.project-osrm.org`) for driving distances, falling back to Haversine distances if OSRM is unavailable.

### 3. Full experimental suite (Phase 1 + Phase 2 + Plots + Recife Map)

Run from the repository root:

```bash
python -m src.experiments.runner
```

Execution pipeline:
1. **Phase 1 (Ablation):** Evaluates `Pure_GA` across all 4 operator pairs `(OX, PMX) × (Swap, Inversion)` on two representative CVRPLIB instances (`A-n32-k5`, `A-n60-k9`) for `--phase1-seeds` runs (default `10`), then selects the pair with the lowest overall mean distance.
2. **Phase 2 (Comparison & Stats):** Runs across all 6 instances (`A-n32-k5`, `A-n45-k6`, `A-n60-k9`, `A-n80-k10`, `Recife-UBS-40-road`, `Recife-UBS-40-haversine`), comparing the deterministic `Greedy` baseline (`seed=0`) against `Pure_GA` and `Memetic_GA` for `--phase2-seeds` runs (default `30`) using the Phase 1 winning operators. Statistical comparison (`phase2_stats_tests.csv`) runs two-sided Wilcoxon signed-rank (paired by seed) and Mann-Whitney U tests between `Pure_GA` and `Memetic_GA` (`significant_005` when `wilcoxon_p < 0.05`).
3. **Charts & Map:** Generates convergence curves, comparative boxplots, and the interactive Folium map (`recife_map.html`) from the best `Memetic_GA` routes on `Recife-UBS-40-road` (querying OSRM for road-snapped polylines with straight-line fallback if offline).

Optional CLI parameters: `--phase1-seeds` (`10`), `--phase2-seeds` (`30`), `--pop-size` (`60`), `--generations` (`150`), `--ls-rate` (`0.30`), `--output-dir` (`results`). Fixed [`GAConfig`](src/solver/genetic.py) defaults: `crossover_rate=0.85`, `mutation_rate=0.20`, `tournament_k=3`, `elite_size=2`, `local_search_max_passes=15`.

Results are saved in `results/`:
- `phase1_ablation.csv`, `phase1_summary.csv`, `phase1_histories.json`
- `phase2_results.csv`, `phase2_summary.csv`, `phase2_stats_tests.csv`
- `phase2_histories.json`, `best_solutions.json`
- `convergence_*.png`, `boxplot_*.png`
- `recife_map.html`

## Output Format & Node Index Mapping (`best_solutions.json`)

[`results/best_solutions.json`](results/best_solutions.json) stores the best route plans per instance and solver (`Greedy`, `Pure_GA`, `Memetic_GA`):

- **Best-of-seeds selection:** For `Pure_GA` and `Memetic_GA`, the saved entry is the single run with the lowest `distance` across all Phase 2 seeds (not an average).
- **Route representation (`routes`):** A `list[list[int]]` where each inner list is one vehicle's ordered sequence of customer visits (`len(routes) == num_vehicles`).
- **Implicit depot (`0`):** The depot index (`0`) is omitted from every inner list; each route implicitly starts and ends at the depot (`0 -> r[0] -> ... -> r[-1] -> 0`).
- **0-based node index mapping:**
  - **Recife (`Recife-UBS-40-road`, `Recife-UBS-40-haversine`):** Indices `0..40` match the 0-based array position in `"nodes"` inside [`data/recife_ubs/recife_ubs.json`](data/recife_ubs/recife_ubs.json) (`0` is `DEPOT-CAF`; `1..40` are the 40 UBS/USF units).
  - **CVRPLIB (`A-n32-k5`, `A-n45-k6`, `A-n60-k9`, `A-n80-k10`):** `.vrp` files use 1-based IDs in `NODE_COORD_SECTION`; [`load_cvrplib`](src/data/cvrplib_loader.py) sorts those IDs and reindexes them to 0-based (`idx = node_id - 1`, so `.vrp` node `1` becomes `0`, node `2` becomes `1`, etc.).
- **Distance units & symmetry:** CVRPLIB distances use TSPLIB `EUC_2D` nearest-integer rounding (`floor(d + 0.5)`). Recife distances are in kilometers (`km`), using geodesic Haversine distances (`Recife-UBS-40-haversine`) or a precomputed OSRM driving matrix (`Recife-UBS-40-road`, which may be asymmetric due to one-way streets).

## Recife Routes Map

Click the map preview below to open the interactive Folium map ([`results/recife_map.html`](results/recife_map.html)) in your browser:

[![Recife UBS/USF Routes Map](results/recife_map_preview.png)](https://lucasmacieel.github.io/cvrp-recife/results/recife_map.html)

> [Open interactive map](https://lucasmacieel.github.io/cvrp-recife/results/recife_map.html) · [View source HTML](results/recife_map.html)
