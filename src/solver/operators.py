"""Evolutionary operators for permutation-based CVRP Giant Tour chromosomes."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np


def tournament_selection(
    fitnesses: np.ndarray,
    k: int,
    rng: np.random.Generator,
) -> int:
    """Select one individual index via k-way tournament (minimization)."""
    pop_size = len(fitnesses)
    tour_size = min(max(1, k), pop_size)
    candidates = rng.choice(pop_size, size=tour_size, replace=False)
    best_idx = int(candidates[np.argmin(fitnesses[candidates])])
    return best_idx


def select_elites(
    population: np.ndarray,
    fitnesses: np.ndarray,
    elite_size: int,
) -> np.ndarray:
    """Return copies of the best `elite_size` individuals (lowest distance)."""
    if elite_size <= 0:
        return np.empty((0, population.shape[1]), dtype=population.dtype)
    order = np.argsort(fitnesses)[:elite_size]
    return population[order].copy()


def _two_cut_points(n: int, rng: np.random.Generator) -> tuple[int, int]:
    a, b = rng.choice(n, size=2, replace=False)
    return (int(a), int(b)) if a < b else (int(b), int(a))


def _ox_single(p1: np.ndarray, p2: np.ndarray, a: int, b: int) -> np.ndarray:
    n = len(p1)
    child = np.full(n, -1, dtype=p1.dtype)
    segment = p1[a : b + 1]
    child[a : b + 1] = segment
    in_segment = set(segment.tolist())

    fill_pos = (b + 1) % n
    for offset in range(n):
        gene = int(p2[(b + 1 + offset) % n])
        if gene not in in_segment:
            child[fill_pos] = gene
            fill_pos = (fill_pos + 1) % n
    return child


def crossover_ox(
    p1: np.ndarray,
    p2: np.ndarray,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    """Order Crossover (OX) producing two valid permutation offspring."""
    n = len(p1)
    if n < 2:
        return p1.copy(), p2.copy()
    a, b = _two_cut_points(n, rng)
    return _ox_single(p1, p2, a, b), _ox_single(p2, p1, a, b)


def _pmx_single(p1: np.ndarray, p2: np.ndarray, a: int, b: int) -> np.ndarray:
    n = len(p1)
    child = np.full(n, -1, dtype=p1.dtype)
    child[a : b + 1] = p1[a : b + 1]

    p2_pos = {int(val): idx for idx, val in enumerate(p2)}
    in_segment = set(p1[a : b + 1].tolist())

    for idx in range(a, b + 1):
        val = int(p2[idx])
        if val not in in_segment:
            cur_idx = idx
            while a <= cur_idx <= b:
                mapped_val = int(p1[cur_idx])
                cur_idx = p2_pos[mapped_val]
            child[cur_idx] = val

    for idx in range(n):
        if child[idx] == -1:
            child[idx] = p2[idx]
    return child


def crossover_pmx(
    p1: np.ndarray,
    p2: np.ndarray,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    """Partially Mapped Crossover (PMX) producing two valid permutation offspring."""
    n = len(p1)
    if n < 2:
        return p1.copy(), p2.copy()
    a, b = _two_cut_points(n, rng)
    return _pmx_single(p1, p2, a, b), _pmx_single(p2, p1, a, b)


def mutate_swap(ind: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Swap mutation: exchange two distinct positions."""
    out = ind.copy()
    if len(out) < 2:
        return out
    i, j = rng.choice(len(out), size=2, replace=False)
    out[i], out[j] = out[j], out[i]
    return out


def mutate_inversion(ind: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Inversion mutation: reverse a random contiguous subsequence."""
    out = ind.copy()
    if len(out) < 2:
        return out
    a, b = _two_cut_points(len(out), rng)
    out[a : b + 1] = out[a : b + 1][::-1]
    return out


CrossoverFn = Callable[[np.ndarray, np.ndarray, np.random.Generator], tuple[np.ndarray, np.ndarray]]
MutationFn = Callable[[np.ndarray, np.random.Generator], np.ndarray]

CROSSOVER_OPERATORS: dict[str, CrossoverFn] = {
    "OX": crossover_ox,
    "PMX": crossover_pmx,
}

MUTATION_OPERATORS: dict[str, MutationFn] = {
    "Swap": mutate_swap,
    "Inversion": mutate_inversion,
}
