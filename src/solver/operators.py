"""Evolutionary operators for permutation-based CVRP Giant Tour chromosomes."""

from __future__ import annotations

import random
from collections.abc import Callable

from deap import tools


def crossover_ox(ind1: list[int], ind2: list[int]) -> tuple[list[int], list[int]]:
    """Order Crossover (OX) via DEAP's ``cxOrdered``, mutating both parents in-place."""
    if len(ind1) < 2 or len(ind2) < 2:
        return ind1, ind2
    return tools.cxOrdered(ind1, ind2)


def crossover_pmx(ind1: list[int], ind2: list[int]) -> tuple[list[int], list[int]]:
    """Partially Mapped Crossover (PMX) via DEAP's ``cxPartialyMatched``, mutating both parents in-place."""
    if len(ind1) < 2 or len(ind2) < 2:
        return ind1, ind2
    return tools.cxPartialyMatched(ind1, ind2)


def mutate_swap(ind: list[int]) -> tuple[list[int]]:
    """Swap mutation: exchange two distinct positions in-place."""
    if len(ind) < 2:
        return (ind,)
    i, j = random.sample(range(len(ind)), 2)
    ind[i], ind[j] = ind[j], ind[i]
    return (ind,)


def mutate_inversion(ind: list[int]) -> tuple[list[int]]:
    """Inversion mutation: reverse a random contiguous subsequence in-place."""
    if len(ind) < 2:
        return (ind,)
    a, b = sorted(random.sample(range(len(ind)), 2))
    ind[a : b + 1] = reversed(ind[a : b + 1])
    return (ind,)


CrossoverFn = Callable[[list[int], list[int]], tuple[list[int], list[int]]]
MutationFn = Callable[[list[int]], tuple[list[int]]]

CROSSOVER_OPERATORS: dict[str, CrossoverFn] = {
    "OX": crossover_ox,
    "PMX": crossover_pmx,
}

MUTATION_OPERATORS: dict[str, MutationFn] = {
    "Swap": mutate_swap,
    "Inversion": mutate_inversion,
}
