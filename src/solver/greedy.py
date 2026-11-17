"""Capacitated Nearest Neighbor greedy baseline solver for CVRP."""

from __future__ import annotations

from dataclasses import dataclass
import time
import numpy as np

from src.data.models import CVRPInstance
from src.solver.decoder import total_distance


@dataclass(frozen=True)
class SolverResult:
    """Unified output returned by CVRP solvers."""

    routes: list[list[int]]
    distance: float
    num_vehicles: int
    runtime_sec: float
    history: list[float] | None = None
    permutation: np.ndarray | None = None


def solve_greedy(instance: CVRPInstance) -> SolverResult:
    """Construct a feasible CVRP solution using Capacitated Nearest Neighbor."""
    t0 = time.perf_counter()

    dist_mat = instance.distance_matrix
    demands = instance.demands
    capacity = instance.capacity
    depot = instance.depot

    unvisited = set(instance.customers)
    routes: list[list[int]] = []

    while unvisited:
        route: list[int] = []
        current = depot
        remaining_cap = capacity

        while unvisited:
            feasible = [c for c in unvisited if int(demands[c]) <= remaining_cap]
            if not feasible:
                break
            # Deterministic tie-breaking by node index
            next_cust = min(feasible, key=lambda c: (float(dist_mat[current, c]), c))
            route.append(next_cust)
            unvisited.remove(next_cust)
            remaining_cap -= int(demands[next_cust])
            current = next_cust

        routes.append(route)

    dist = total_distance(routes, dist_mat, depot)
    elapsed = time.perf_counter() - t0
    perm = np.array([c for r in routes for c in r], dtype=np.int64)

    return SolverResult(
        routes=routes,
        distance=dist,
        num_vehicles=len(routes),
        runtime_sec=elapsed,
        history=None,
        permutation=perm,
    )
