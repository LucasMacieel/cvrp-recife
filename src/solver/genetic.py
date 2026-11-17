"""Pure and Memetic (Lamarckian 2-opt) Genetic Algorithm solvers for CVRP."""

from __future__ import annotations

from dataclasses import dataclass
import time
import numpy as np

from src.data.models import CVRPInstance
from src.solver.decoder import decode_giant_tour, evaluate_giant_tour
from src.solver.greedy import SolverResult
from src.solver.local_search import lamarckian_two_opt
from src.solver.operators import (
    CROSSOVER_OPERATORS,
    MUTATION_OPERATORS,
    select_elites,
    tournament_selection,
)


@dataclass(frozen=True)
class GAConfig:
    """Hyperparameters for the Genetic and Memetic CVRP solvers."""

    pop_size: int = 60
    generations: int = 150
    crossover_rate: float = 0.85
    mutation_rate: float = 0.20
    tournament_k: int = 3
    elite_size: int = 2
    crossover: str = "OX"
    mutation: str = "Inversion"
    memetic: bool = False
    local_search_rate: float = 0.30
    local_search_max_passes: int = 15
    seed: int = 42


def solve_genetic(
    instance: CVRPInstance,
    config: GAConfig | None = None,
) -> SolverResult:
    """Solve CVRP using a Giant Tour Genetic Algorithm (optionally Memetic)."""
    cfg = config or GAConfig()
    if cfg.crossover not in CROSSOVER_OPERATORS:
        raise ValueError(
            f"Unknown crossover {cfg.crossover!r}; choose from {list(CROSSOVER_OPERATORS)}"
        )
    if cfg.mutation not in MUTATION_OPERATORS:
        raise ValueError(
            f"Unknown mutation {cfg.mutation!r}; choose from {list(MUTATION_OPERATORS)}"
        )

    t0 = time.perf_counter()
    rng = np.random.default_rng(cfg.seed)
    cx_fn = CROSSOVER_OPERATORS[cfg.crossover]
    mut_fn = MUTATION_OPERATORS[cfg.mutation]
    is_sym = instance.is_symmetric

    customers = np.array(instance.customers, dtype=np.int64)
    n_cust = len(customers)

    population = np.array(
        [rng.permutation(customers) for _ in range(cfg.pop_size)],
        dtype=np.int64,
    )
    fitnesses = np.array(
        [evaluate_giant_tour(ind, instance) for ind in population],
        dtype=np.float64,
    )

    if cfg.memetic:
        best_idx = int(np.argmin(fitnesses))
        population[best_idx], fitnesses[best_idx] = lamarckian_two_opt(
            population[best_idx],
            instance,
            symmetric=is_sym,
            max_passes=cfg.local_search_max_passes,
        )

    history: list[float] = [float(np.min(fitnesses))]

    for _gen in range(cfg.generations):
        elites = select_elites(population, fitnesses, cfg.elite_size)
        new_pop_list: list[np.ndarray] = [e for e in elites]

        while len(new_pop_list) < cfg.pop_size:
            i1 = tournament_selection(fitnesses, cfg.tournament_k, rng)
            i2 = tournament_selection(fitnesses, cfg.tournament_k, rng)
            p1, p2 = population[i1], population[i2]

            if rng.random() < cfg.crossover_rate:
                c1, c2 = cx_fn(p1, p2, rng)
            else:
                c1, c2 = p1.copy(), p2.copy()

            if rng.random() < cfg.mutation_rate:
                c1 = mut_fn(c1, rng)
            if rng.random() < cfg.mutation_rate:
                c2 = mut_fn(c2, rng)

            for child in (c1, c2):
                if len(new_pop_list) >= cfg.pop_size:
                    break
                if cfg.memetic and rng.random() < cfg.local_search_rate:
                    child, _ = lamarckian_two_opt(
                        child,
                        instance,
                        symmetric=is_sym,
                        max_passes=cfg.local_search_max_passes,
                    )
                new_pop_list.append(child)

        population = np.asarray(new_pop_list, dtype=np.int64).reshape(cfg.pop_size, n_cust)
        fitnesses = np.array(
            [evaluate_giant_tour(ind, instance) for ind in population],
            dtype=np.float64,
        )

        if cfg.memetic:
            best_idx = int(np.argmin(fitnesses))
            population[best_idx], fitnesses[best_idx] = lamarckian_two_opt(
                population[best_idx],
                instance,
                symmetric=is_sym,
                max_passes=cfg.local_search_max_passes,
            )

        history.append(float(np.min(fitnesses)))

    best_idx = int(np.argmin(fitnesses))
    best_perm = population[best_idx].copy()
    best_routes, best_dist = decode_giant_tour(best_perm, instance)
    elapsed = time.perf_counter() - t0

    return SolverResult(
        routes=best_routes,
        distance=best_dist,
        num_vehicles=len(best_routes),
        runtime_sec=elapsed,
        history=history,
        permutation=best_perm,
    )
