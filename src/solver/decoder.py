"""Giant Tour greedy capacity-split decoder and route distance evaluation."""

from __future__ import annotations

from typing import Sequence
import numpy as np

from src.data.models import CVRPInstance


def route_distance(
    route: Sequence[int],
    distance_matrix: np.ndarray,
    depot: int = 0,
) -> float:
    """Compute the closed distance of a single customer route starting/ending at depot."""
    if not route:
        return 0.0
    dist = float(distance_matrix[depot, route[0]])
    for i in range(len(route) - 1):
        dist += float(distance_matrix[route[i], route[i + 1]])
    dist += float(distance_matrix[route[-1], depot])
    return dist


def total_distance(
    routes: Sequence[Sequence[int]],
    distance_matrix: np.ndarray,
    depot: int = 0,
) -> float:
    """Compute total distance across all routes."""
    return sum(route_distance(r, distance_matrix, depot) for r in routes)


def decode_giant_tour(
    permutation: Sequence[int] | np.ndarray,
    instance: CVRPInstance,
) -> tuple[list[list[int]], float]:
    """Decode a Giant Tour customer permutation into feasible routes via greedy split.

    Args:
        permutation: Sequence of customer node indices (all N - 1 non-depot nodes).
        instance: Validated CVRPInstance.

    Returns:
        Tuple of (routes, total_dist), where each route is a list of customer indices.
    """
    demands = instance.demands
    capacity = instance.capacity
    depot = instance.depot
    dist_mat = instance.distance_matrix

    routes: list[list[int]] = []
    current_route: list[int] = []
    current_load = 0

    for node in permutation:
        cust = int(node)
        demand = int(demands[cust])
        if current_route and current_load + demand > capacity:
            routes.append(current_route)
            current_route = [cust]
            current_load = demand
        else:
            current_route.append(cust)
            current_load += demand

    if current_route:
        routes.append(current_route)

    return routes, total_distance(routes, dist_mat, depot)


def evaluate_giant_tour(
    permutation: Sequence[int] | np.ndarray,
    instance: CVRPInstance,
) -> float:
    """Fast distance-only evaluation of a Giant Tour permutation."""
    demands = instance.demands
    capacity = instance.capacity
    depot = instance.depot
    dist_mat = instance.distance_matrix

    total = 0.0
    prev = depot
    current_load = 0
    has_active = False

    for node in permutation:
        cust = int(node)
        demand = int(demands[cust])
        if has_active and current_load + demand > capacity:
            total += float(dist_mat[prev, depot])
            prev = depot
            current_load = demand
        else:
            current_load += demand
        total += float(dist_mat[prev, cust])
        prev = cust
        has_active = True

    if has_active:
        total += float(dist_mat[prev, depot])

    return total


def validate_routes(routes: Sequence[Sequence[int]], instance: CVRPInstance) -> None:
    """Raise ValueError if routes violate capacity or customer coverage constraints."""
    visited: list[int] = []
    for idx, route in enumerate(routes):
        if not route:
            raise ValueError(f"Route {idx} is empty")
        load = int(sum(instance.demands[c] for c in route))
        if load > instance.capacity:
            raise ValueError(
                f"Route {idx} exceeds capacity: {load} > {instance.capacity}"
            )
        visited.extend(int(c) for c in route)

    expected = sorted(instance.customers)
    if sorted(visited) != expected:
        raise ValueError("Routes must visit every customer exactly once without depot")
