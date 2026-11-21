"""Unit tests for CVRP decoder, greedy baseline, genetic operators, and 2-opt."""

from __future__ import annotations

import random

import numpy as np
import pytest

from src.data.cvrplib_loader import load_cvrplib
from src.data.models import CVRPInstance
from src.data.recife_loader import load_recife
from src.solver.decoder import (
    decode_giant_tour,
    evaluate_giant_tour,
    total_distance,
    validate_routes,
)
from src.solver.genetic import GAConfig, solve_genetic
from src.solver.greedy import solve_greedy
from src.solver.local_search import lamarckian_two_opt, two_opt_solution
from src.solver.operators import (
    CROSSOVER_OPERATORS,
    MUTATION_OPERATORS,
)


def _toy_instance() -> CVRPInstance:
    # Depot 0 at (0,0), customers 1..4
    coords = np.array([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0], [0.0, 3.0], [0.0, 4.0]])
    diff = coords[:, None, :] - coords[None, :, :]
    dist = np.hypot(diff[:, :, 0], diff[:, :, 1])
    return CVRPInstance(
        name="toy-5",
        distance_matrix=dist,
        demands=np.array([0, 6, 6, 5, 5]),
        capacity=10,
        depot=0,
        coords=coords,
    )


def test_decode_giant_tour_respects_capacity_and_coverage() -> None:
    inst = _toy_instance()
    perm = np.array([1, 2, 3, 4])
    routes, dist = decode_giant_tour(perm, inst)
    validate_routes(routes, inst)
    # 1(6) -> [1], 2(6) exceeds 10 -> [2], 3(5) exceeds 10 -> [3, 4](10)
    assert routes == [[1], [2], [3, 4]]
    assert np.isclose(dist, total_distance(routes, inst.distance_matrix, inst.depot))
    assert np.isclose(dist, evaluate_giant_tour(perm, inst))


def test_decode_giant_tour_on_cvrplib_a_n32_k5() -> None:
    inst = load_cvrplib("data/cvrplib/A-n32-k5.vrp")
    rng = np.random.default_rng(123)
    for _ in range(10):
        perm = rng.permutation(inst.customers)
        routes, dist = decode_giant_tour(perm, inst)
        validate_routes(routes, inst)
        assert np.isclose(dist, evaluate_giant_tour(perm, inst))


def test_greedy_baseline_toy_and_cvrplib() -> None:
    toy = _toy_instance()
    res_toy = solve_greedy(toy)
    validate_routes(res_toy.routes, toy)
    assert np.isclose(
        res_toy.distance, total_distance(res_toy.routes, toy.distance_matrix, toy.depot)
    )
    assert res_toy.num_vehicles == len(res_toy.routes)
    assert res_toy.runtime_sec >= 0.0

    inst = load_cvrplib("data/cvrplib/A-n32-k5.vrp")
    res = solve_greedy(inst)
    validate_routes(res.routes, inst)
    assert np.isclose(
        res.distance, total_distance(res.routes, inst.distance_matrix, inst.depot)
    )
    assert inst.optimal_value is not None
    assert res.distance >= inst.optimal_value


@pytest.mark.parametrize("cx_name", ["OX", "PMX"])
@pytest.mark.parametrize("mut_name", ["Swap", "Inversion"])
def test_operators_preserve_valid_permutations(cx_name: str, mut_name: str) -> None:
    py_rng = random.Random(7)
    base = list(range(31))
    expected = set(base)
    cx_fn = CROSSOVER_OPERATORS[cx_name]
    mut_fn = MUTATION_OPERATORS[mut_name]

    for _ in range(100):
        p1 = py_rng.sample(base, len(base))
        p2 = py_rng.sample(base, len(base))
        c1, c2 = cx_fn(p1, p2)
        (m1,) = mut_fn(c1[:])
        (m2,) = mut_fn(c2[:])
        for child in (c1, c2, m1, m2):
            assert isinstance(child, list)
            assert len(child) == len(base)
            assert set(child) == expected


@pytest.mark.parametrize("cx_name", ["OX", "PMX"])
@pytest.mark.parametrize("mut_name", ["Swap", "Inversion"])
@pytest.mark.parametrize("n", [0, 1])
def test_operators_short_permutations(cx_name: str, mut_name: str, n: int) -> None:
    cx_fn = CROSSOVER_OPERATORS[cx_name]
    mut_fn = MUTATION_OPERATORS[mut_name]
    p1 = list(range(n))
    p2 = list(range(n))
    c1, c2 = cx_fn(p1, p2)
    assert c1 == list(range(n))
    assert c2 == list(range(n))
    (m1,) = mut_fn(c1)
    assert m1 == list(range(n))


def test_genetic_reproducibility_and_convergence() -> None:
    inst = load_cvrplib("data/cvrplib/A-n32-k5.vrp")
    cfg = GAConfig(
        pop_size=20, generations=25, crossover="OX", mutation="Inversion", seed=99
    )

    r1 = solve_genetic(inst, cfg)
    r2 = solve_genetic(inst, cfg)

    validate_routes(r1.routes, inst)
    assert r1.distance == r2.distance
    assert r1.routes == r2.routes
    assert r1.history == r2.history
    assert r1.history is not None
    assert len(r1.history) == 26
    assert all(
        r1.history[i] >= r1.history[i + 1] - 1e-12 for i in range(len(r1.history) - 1)
    )


def test_two_opt_never_worsens_symmetric_and_asymmetric() -> None:
    inst_sym = load_cvrplib("data/cvrplib/A-n32-k5.vrp")
    rng = np.random.default_rng(12)
    perm = rng.permutation(inst_sym.customers)
    routes, orig_dist = decode_giant_tour(perm, inst_sym)
    opt_routes, opt_dist = two_opt_solution(routes, inst_sym)
    validate_routes(opt_routes, inst_sym)
    assert opt_dist <= orig_dist + 1e-12

    # Asymmetric 5-node instance
    asym = np.array(
        [
            [0.0, 2.0, 9.0, 10.0, 7.0],
            [8.0, 0.0, 1.0, 6.0, 4.0],
            [5.0, 9.0, 0.0, 2.0, 8.0],
            [3.0, 7.0, 9.0, 0.0, 1.0],
            [1.0, 5.0, 8.0, 9.0, 0.0],
        ]
    )
    inst_asym = CVRPInstance(
        name="asym-5",
        distance_matrix=asym,
        demands=np.array([0, 2, 2, 2, 2]),
        capacity=10,
        depot=0,
    )
    assert inst_asym.is_symmetric is False
    bad_perm = np.array([4, 3, 2, 1])
    _, d_before = decode_giant_tour(bad_perm, inst_asym)
    new_perm, d_after = lamarckian_two_opt(bad_perm, inst_asym)
    new_routes, d_check = decode_giant_tour(new_perm, inst_asym)
    validate_routes(new_routes, inst_asym)
    assert d_after <= d_before + 1e-12
    assert np.isclose(d_after, d_check)


def _boundary_shift_instance(edge_2_5: float) -> CVRPInstance:
    """Construct a symmetric 6-customer instance where 2-opt shifts greedy-split boundaries."""
    dist = np.ones((7, 7), dtype=float)
    np.fill_diagonal(dist, 0.0)
    dist[0, 3] = dist[3, 0] = 10.0
    dist[5, 6] = dist[6, 5] = 10.0
    dist[2, 5] = dist[5, 2] = edge_2_5
    return CVRPInstance(
        name="boundary-shift",
        distance_matrix=dist,
        demands=np.array([0, 4, 4, 5, 1, 2, 2]),
        capacity=10,
        depot=0,
    )


def test_lamarckian_two_opt_rejects_worsening_boundary_shift() -> None:
    inst = _boundary_shift_instance(edge_2_5=100.0)
    perm = np.array([1, 2, 3, 4, 5, 6], dtype=np.int64)
    routes, orig_dist = decode_giant_tour(perm, inst)
    assert routes == [[1, 2], [3, 4, 5, 6]]

    improved_routes, two_opt_dist = two_opt_solution(routes, inst)
    assert two_opt_dist < orig_dist - 1e-12
    shifted_perm = np.array([c for r in improved_routes for c in r], dtype=np.int64)
    assert evaluate_giant_tour(shifted_perm, inst) > orig_dist

    out_perm, out_dist = lamarckian_two_opt(perm, inst)
    assert np.array_equal(out_perm, perm)
    assert np.isclose(out_dist, orig_dist, atol=1e-12)


def test_lamarckian_two_opt_returns_redecoded_distance_on_improving_boundary_shift() -> (
    None
):
    inst = _boundary_shift_instance(edge_2_5=5.0)
    perm = np.array([1, 2, 3, 4, 5, 6], dtype=np.int64)
    routes, orig_dist = decode_giant_tour(perm, inst)

    improved_routes, two_opt_dist = two_opt_solution(routes, inst)
    shifted_perm = np.array([c for r in improved_routes for c in r], dtype=np.int64)
    expected_redecoded = evaluate_giant_tour(shifted_perm, inst)
    assert two_opt_dist < expected_redecoded < orig_dist - 1e-12

    out_perm, out_dist = lamarckian_two_opt(perm, inst)
    assert np.array_equal(out_perm, shifted_perm)
    assert np.isclose(out_dist, expected_redecoded, atol=1e-12)
    assert not np.isclose(out_dist, two_opt_dist, atol=1e-6)


@pytest.mark.parametrize(
    "loader",
    [
        lambda: load_cvrplib("data/cvrplib/A-n32-k5.vrp"),
        lambda: load_recife("data/recife_ubs"),
    ],
)
def test_lamarckian_two_opt_randomized_multi_route_probes(loader) -> None:
    inst = loader()
    rng = np.random.default_rng(2025)
    for _ in range(15):
        perm = rng.permutation(inst.customers)
        d_before = evaluate_giant_tour(perm, inst)
        new_perm, d_after = lamarckian_two_opt(perm, inst)
        new_routes, _ = decode_giant_tour(new_perm, inst)
        validate_routes(new_routes, inst)
        assert np.isclose(d_after, evaluate_giant_tour(new_perm, inst), atol=1e-12)
        assert d_after <= d_before + 1e-12


def test_memetic_genetic_solver() -> None:
    inst = load_cvrplib("data/cvrplib/A-n32-k5.vrp")
    cfg = GAConfig(
        pop_size=20,
        generations=15,
        crossover="PMX",
        mutation="Swap",
        memetic=True,
        local_search_rate=0.5,
        seed=42,
    )
    res = solve_genetic(inst, cfg)
    validate_routes(res.routes, inst)
    assert res.history is not None and len(res.history) == 16
    assert res.distance <= res.history[0] + 1e-12


def test_genetic_isolates_global_random_state() -> None:
    inst = _toy_instance()
    cfg = GAConfig(pop_size=10, generations=5, seed=77)

    random.seed(12345)
    expected_stream = [random.random() for _ in range(10)]

    random.seed(12345)
    solve_genetic(inst, cfg)
    actual_stream = [random.random() for _ in range(10)]

    assert actual_stream == expected_stream


@pytest.mark.parametrize(
    ("cx_name", "mut_name"),
    [("OX", "Swap"), ("PMX", "Inversion")],
)
def test_genetic_nonzero_depot_index(cx_name: str, mut_name: str) -> None:
    coords = np.array([[1.0, 0.0], [2.0, 0.0], [0.0, 0.0], [0.0, 3.0], [0.0, 4.0]])
    diff = coords[:, None, :] - coords[None, :, :]
    dist = np.hypot(diff[:, :, 0], diff[:, :, 1])
    inst = CVRPInstance(
        name="nonzero-depot-5",
        distance_matrix=dist,
        demands=np.array([3, 3, 0, 2, 2]),
        capacity=5,
        depot=2,
        coords=coords,
    )
    cfg = GAConfig(
        pop_size=12,
        generations=10,
        crossover=cx_name,
        mutation=mut_name,
        memetic=True,
        seed=11,
    )
    res = solve_genetic(inst, cfg)
    validate_routes(res.routes, inst)
    assert res.permutation is not None
    assert set(res.permutation.tolist()) == {0, 1, 3, 4}


@pytest.mark.parametrize(
    ("pop_size", "elite_size"),
    [(10, 0), (11, 2), (10, 15)],
)
def test_genetic_elite_size_edge_cases(pop_size: int, elite_size: int) -> None:
    inst = _toy_instance()
    cfg = GAConfig(
        pop_size=pop_size,
        generations=8,
        elite_size=elite_size,
        seed=5,
    )
    res = solve_genetic(inst, cfg)
    validate_routes(res.routes, inst)
    assert res.history is not None and len(res.history) == 9
    assert res.distance <= min(res.history) + 1e-12
    if elite_size >= 1:
        assert all(
            res.history[i] >= res.history[i + 1] - 1e-12
            for i in range(len(res.history) - 1)
        )


@pytest.mark.parametrize(
    ("instance_path", "is_recife", "seed", "elite_size"),
    [
        ("data/cvrplib/A-n32-k5.vrp", False, 42, 2),
        ("data/cvrplib/A-n32-k5.vrp", False, 7, 0),
        ("data/recife_ubs", True, 1, 2),
        ("data/recife_ubs", True, 13, 2),
        ("data/recife_ubs", True, 1, 0),
    ],
)
def test_memetic_genetic_consistency_and_monotonicity(
    instance_path: str, is_recife: bool, seed: int, elite_size: int
) -> None:
    inst = load_recife(instance_path) if is_recife else load_cvrplib(instance_path)
    cfg = GAConfig(
        pop_size=20,
        generations=20,
        elite_size=elite_size,
        memetic=True,
        local_search_rate=0.5,
        seed=seed,
    )
    res = solve_genetic(inst, cfg)
    validate_routes(res.routes, inst)
    assert res.history is not None and len(res.history) == 21
    assert res.permutation is not None
    assert np.isclose(
        res.distance, evaluate_giant_tour(res.permutation, inst), atol=1e-12
    )
    if elite_size >= 1:
        assert all(
            res.history[i] >= res.history[i + 1] - 1e-12
            for i in range(len(res.history) - 1)
        )
        assert np.isclose(res.distance, res.history[-1], atol=1e-12)
    else:
        assert res.distance <= min(res.history) + 1e-12
