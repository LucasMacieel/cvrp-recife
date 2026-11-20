"""Intra-route 2-opt local search supporting symmetric and asymmetric matrices."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from src.data.models import CVRPInstance
from src.solver.decoder import decode_giant_tour, total_distance


def _segment_cost(
    nodes: Sequence[int],
    dist_mat: np.ndarray,
    prev_node: int,
    next_node: int,
) -> float:
    cost = float(dist_mat[prev_node, nodes[0]])
    for k in range(len(nodes) - 1):
        cost += float(dist_mat[nodes[k], nodes[k + 1]])
    cost += float(dist_mat[nodes[-1], next_node])
    return cost


def two_opt_route(
    route: Sequence[int],
    distance_matrix: np.ndarray,
    depot: int = 0,
    *,
    symmetric: bool = True,
    max_passes: int = 20,
) -> list[int]:
    """Improve a single route using best-improvement intra-route 2-opt."""
    cur = [int(x) for x in route]
    m = len(cur)
    if m < 2 or (symmetric and m < 3):
        return cur

    eps = 1e-12
    for _ in range(max_passes):
        best_delta = -eps
        best_move: tuple[int, int] | None = None

        for i in range(m - 1):
            prev_i = depot if i == 0 else cur[i - 1]
            for j in range(i + 1, m):
                next_j = depot if j == m - 1 else cur[j + 1]
                if symmetric:
                    old_cost = float(
                        distance_matrix[prev_i, cur[i]] + distance_matrix[cur[j], next_j]
                    )
                    new_cost = float(
                        distance_matrix[prev_i, cur[j]] + distance_matrix[cur[i], next_j]
                    )
                else:
                    sub = cur[i : j + 1]
                    old_cost = _segment_cost(sub, distance_matrix, prev_i, next_j)
                    new_cost = _segment_cost(sub[::-1], distance_matrix, prev_i, next_j)

                delta = new_cost - old_cost
                if delta < best_delta:
                    best_delta = delta
                    best_move = (i, j)

        if best_move is None:
            break
        bi, bj = best_move
        cur[bi : bj + 1] = cur[bi : bj + 1][::-1]

    return cur


def two_opt_solution(
    routes: Sequence[Sequence[int]],
    instance: CVRPInstance,
    *,
    symmetric: bool | None = None,
    max_passes: int = 20,
) -> tuple[list[list[int]], float]:
    """Apply intra-route 2-opt to every route of a feasible CVRP solution."""
    is_sym = instance.is_symmetric if symmetric is None else symmetric
    improved = [
        two_opt_route(
            r,
            instance.distance_matrix,
            instance.depot,
            symmetric=is_sym,
            max_passes=max_passes,
        )
        for r in routes
    ]
    return improved, total_distance(improved, instance.distance_matrix, instance.depot)


def lamarckian_two_opt(
    permutation: np.ndarray,
    instance: CVRPInstance,
    *,
    symmetric: bool | None = None,
    max_passes: int = 20,
) -> tuple[np.ndarray, float]:
    """Apply 2-opt to decoded routes and write back only on strict improvement."""
    routes, orig_dist = decode_giant_tour(permutation, instance)
    improved_routes, new_dist = two_opt_solution(
        routes, instance, symmetric=symmetric, max_passes=max_passes
    )
    if new_dist < orig_dist - 1e-12:
        new_perm = np.array(
            [c for route in improved_routes for c in route],
            dtype=permutation.dtype,
        )
        return new_perm, new_dist
    return permutation, orig_dist
