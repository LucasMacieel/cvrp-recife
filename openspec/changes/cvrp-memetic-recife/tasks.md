# Tasks

## 1. Project Structure and Dependencies

- [x] 1.1 Create the initial directory structure (`src/data/`, `src/solver/`, `src/experiments/`, `data/cvrplib/`, `data/recife_ubs/`, `scripts/`, `tests/`, `results/`) and `pyproject.toml`/`requirements.txt` with `numpy`, `scipy`, `matplotlib`, `folium`, and `pytest`, verifying that `pytest --version` and `python -c "import numpy, scipy, matplotlib, folium"` run without errors.

## 2. Data and Unified Loaders (`cvrp-data-loading`)

- [x] 2.1 Define the `CVRPInstance` `dataclass` and its integrity validations (`N x N` matrix dimensions, no `NaN`/negative values, `0` demand at the depot, and no individual demand greater than `Q`) in `src/data/models.py`, verifying with unit tests in `tests/test_data_loading.py` covering valid cases and expected errors.
- [x] 2.2 Download and version 4 classical CVRPLIB instances (`A-n32-k5`, `A-n45-k6`, `A-n60-k9`, `A-n80-k10`) with their respective known optima in `data/cvrplib/`, implement the `EUC_2D` parser in `src/data/cvrplib_loader.py`, and verify via `pytest tests/test_data_loading.py` that dimensions, demands, and symmetric matrix match the `.vrp` files.
- [x] 2.3 Create `scripts/prepare_recife_data.py` to consolidate real coordinates of 30 to 45 UBSs/Polyclinics in Recife/PE (Recife Open Data / OpenStreetMap) + central depot and pre-compute the road distance matrix (OSRM, with Haversine fallback) into `data/recife_ubs/recife_ubs.json` and `data/recife_ubs/distance_matrix_road.npy`, verifying that the files are generated and load offline via `src/data/recife_loader.py`.
- [x] 2.4 Implement support in `src/data/recife_loader.py` for `road` distance mode (pre-computed matrix) and `haversine` mode (geodesic calculation in km), covering both modes with tests in `tests/test_data_loading.py`.

## 3. CVRP Optimization Engine (`memetic-cvrp-solver`)

- [x] 3.1 Implement Giant Tour decoding with capacity-constrained greedy Split and total distance calculation in `src/solver/decoder.py`, verifying with `pytest tests/test_solver.py` that no route exceeds `Q` and all customers are visited exactly once.
- [x] 3.2 Implement the capacitated Nearest Neighbor baseline heuristic in `src/solver/greedy.py`, verifying via `pytest tests/test_solver.py` route feasibility and total distance consistency on small instances and `A-n32-k5`.
- [x] 3.3 Implement tournament selection, elitism, `OX` and `PMX` crossovers, and `Swap` and `Inversion` mutations using `numpy.random.Generator` in `src/solver/operators.py`, verifying with `pytest tests/test_solver.py` that 100% of generated offspring are valid permutations without repetitions or omissions.
- [x] 3.4 Implement the Pure Genetic Algorithm in `src/solver/genetic.py` recording the best distance history per generation and verify exact reproducibility (same seed yields identical solution and history) via `pytest tests/test_solver.py`.
- [x] 3.5 Implement intra-route `2-opt` local search (correctly handling both symmetric and asymmetric matrices) in `src/solver/local_search.py` and integrate it as Lamarckian Memetic mode in `src/solver/genetic.py`, verifying via `pytest tests/test_solver.py` that `2-opt` never increases route cost or violates `Q`.

## 4. Experimentation, Statistics, and Visualizations (`experiment-benchmarking`)

- [x] 4.1 Implement the campaign runner in `src/experiments/runner.py` supporting Phase 1 (`OX`/`PMX` x `Swap`/`Inversion` ablation across 10 seeds) and Phase 2 (Greedy vs. Pure GA vs. Memetic GA comparison across 30 seeds on CVRPLIB and Recife `road`/`haversine` instances), saving raw CSVs in `results/` and verifying with a quick smoke test (2 seeds, few generations) via `pytest tests/test_experiments.py`.
- [x] 4.2 Implement the aggregation and statistical testing module in `src/experiments/stats.py` (mean, standard deviation, best, worst, % gap vs. known optimum, and Wilcoxon/Mann-Whitney tests via `scipy.stats`), verifying exact gap and p-value calculations in `tests/test_experiments.py`.
- [x] 4.3 Implement `src/experiments/plots.py` (mean +/- std convergence curves and comparative boxplots) and `src/experiments/map_recife.py` (`folium` HTML map with depot, UBSs/Polyclinics, and color-coded vehicle routes), verifying error-free `.png` and `.html` generation in the smoke test.
- [x] 4.4 Run the full experimental suite (Phase 1 + Phase 2 + Recife), document execution commands and project structure in `README.md`, and verify that all final artifacts (CSV tables, PNG charts, and `results/recife_map.html`) were generated and all tests pass with `pytest`.
