"""Pure and Memetic (Lamarckian 2-opt) Genetic Algorithm solvers for CVRP using DEAP."""

from __future__ import annotations

import random
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
from deap import algorithms, base, creator, tools

from src.data.models import CVRPInstance
from src.solver.decoder import decode_giant_tour, evaluate_giant_tour
from src.solver.greedy import SolverResult
from src.solver.local_search import lamarckian_two_opt
from src.solver.operators import CROSSOVER_OPERATORS, MUTATION_OPERATORS

_creator: Any = creator
if not hasattr(_creator, "FitnessMin"):
    _creator.create("FitnessMin", base.Fitness, weights=(-1.0,))
if not hasattr(_creator, "Individual"):
    _creator.create("Individual", list, fitness=_creator.FitnessMin)


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
    """Solve CVRP using a DEAP-backed Giant Tour Genetic Algorithm (optionally Memetic)."""
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
    is_sym = instance.is_symmetric
    customers = [int(c) for c in instance.customers]
    n_cust = len(customers)
    cust_to_idx = {cust: idx for idx, cust in enumerate(customers)}

    n_elites = min(max(0, cfg.elite_size), cfg.pop_size)
    n_offspring = cfg.pop_size - n_elites
    tournsize = min(max(1, cfg.tournament_k), cfg.pop_size)

    def _to_customers(ind: Sequence[int]) -> list[int]:
        return [customers[i] for i in ind]

    def _apply_local_search(ind: Any) -> None:
        improved_perm, dist = lamarckian_two_opt(
            np.array(_to_customers(ind), dtype=np.int64),
            instance,
            symmetric=is_sym,
            max_passes=cfg.local_search_max_passes,
        )
        ind[:] = [cust_to_idx[int(c)] for c in improved_perm]
        ind.fitness.values = (dist,)

    toolbox: Any = base.Toolbox()
    toolbox.register("indices", random.sample, range(n_cust), n_cust)
    toolbox.register(
        "individual", tools.initIterate, _creator.Individual, toolbox.indices
    )
    toolbox.register("population", tools.initRepeat, list, toolbox.individual)
    toolbox.register(
        "evaluate", lambda ind: (evaluate_giant_tour(_to_customers(ind), instance),)
    )
    toolbox.register("mate", CROSSOVER_OPERATORS[cfg.crossover])
    toolbox.register("mutate", MUTATION_OPERATORS[cfg.mutation])
    toolbox.register("select", tools.selTournament, tournsize=tournsize)

    stats = tools.Statistics(lambda ind: ind.fitness.values[0])
    stats.register("min", min)
    logbook = tools.Logbook()
    hof = tools.HallOfFame(1)

    rng_state = random.getstate()
    try:
        random.seed(cfg.seed)

        population = toolbox.population(n=cfg.pop_size)
        for ind in population:
            ind.fitness.values = toolbox.evaluate(ind)

        if cfg.memetic and population:
            best_ind = min(population, key=lambda ind: ind.fitness.values[0])
            _apply_local_search(best_ind)

        hof.update(population)
        logbook.record(gen=0, **stats.compile(population))

        for gen in range(1, cfg.generations + 1):
            elites = (
                list(map(toolbox.clone, tools.selBest(population, n_elites)))
                if n_elites > 0
                else []
            )
            selected = toolbox.select(population, n_offspring)
            offspring = algorithms.varAnd(
                selected,
                toolbox,
                cxpb=cfg.crossover_rate,
                mutpb=cfg.mutation_rate,
            )

            if cfg.memetic:
                for child in offspring:
                    if random.random() < cfg.local_search_rate:
                        _apply_local_search(child)

            for ind in offspring:
                if not ind.fitness.valid:
                    ind.fitness.values = toolbox.evaluate(ind)

            population[:] = elites + offspring

            if cfg.memetic and population:
                best_ind = min(population, key=lambda ind: ind.fitness.values[0])
                _apply_local_search(best_ind)

            hof.update(population)
            logbook.record(gen=gen, **stats.compile(population))

        best_ind = hof[0]
        best_perm = np.array(_to_customers(best_ind), dtype=np.int64)
        best_routes, best_dist = decode_giant_tour(best_perm, instance)
        history = [float(val) for val in logbook.select("min")]
    finally:
        random.setstate(rng_state)

    elapsed = time.perf_counter() - t0

    return SolverResult(
        routes=best_routes,
        distance=best_dist,
        num_vehicles=len(best_routes),
        runtime_sec=elapsed,
        history=history,
        permutation=best_perm,
    )
