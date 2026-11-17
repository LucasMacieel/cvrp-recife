# Proposal

## Why

Distributing medicines and medical supplies from a central depot to Primary Health Units (UBSs) and Polyclinics in Recife/PE requires planning capacitated vehicle routes that minimize total distance traveled across an urban road network intersected by rivers and bridges. This project applies Evolutionary Computation methods (a Pure Genetic Algorithm and a Memetic Genetic Algorithm with intra-route `2-opt` local search) to solve this real-world Capacitated Vehicle Routing Problem (CVRP), validating the approach on scientific benchmarks (CVRPLIB) and on a real geographic scenario of Recife for rigorous experimental analysis in the Computational Intelligence course.

## What Changes

- Introduces a unified CVRP instance loader that converts both standard CVRPLIB files (`EUC_2D`) and real UBS/Polyclinic data from Recife/PE (pre-computed OSRM road matrix with Haversine fallback) into a common representation of distance matrix, demands, and capacity.
- Implements from scratch, in Python and NumPy, three comparative approaches for CVRP: a greedy heuristic (Nearest Neighbor), a Pure Genetic Algorithm (Giant Tour + capacity-constrained Split, `OX`/`PMX` crossovers, and `Swap`/`Inversion` mutations), and a Memetic Genetic Algorithm (GA + intra-route `2-opt`).
- Adds an automated multi-seed experimentation suite with metric export (total distance, percentage gap vs. known optimum, runtime, convergence curves), non-parametric statistical tests, and route visualization on an interactive map of Recife.

## Capabilities

### New Capabilities

- `cvrp-data-loading`: Loading, validation, and normalization of CVRPLIB instances (`.vrp`) and the geographic UBS/Polyclinic dataset of Recife/PE into a distance matrix and capacity constraints.
- `memetic-cvrp-solver`: CVRP solvers implemented in Python + NumPy (Greedy Baseline, Pure Genetic Algorithm, and Memetic Genetic Algorithm with intra-route `2-opt`), guaranteeing feasibility by construction via greedy Split.
- `experiment-benchmarking`: Orchestration of reproducible multi-seed experiments, comparative statistical analysis, benchmark gap computation, convergence plots, and interactive maps of the routes in Recife.

### Modified Capabilities

<!-- No existing capabilities modified; initial project with no prior specs. -->

## Impact

- New structured Python code in the repository (`src/`, `data/`, `experiments/`, `tests/`).
- Planned dependencies: Python 3.10+, `numpy`, `scipy` (statistical tests), `matplotlib` (convergence/boxplot charts), `folium` (interactive Recife map), and `pytest` (unit tests).
- Versioned local data files (selected CVRPLIB `.vrp` instances and pre-processed static dataset of Recife UBSs/Polyclinics with road distance matrix) to ensure 100% offline reproducibility of experiments.
