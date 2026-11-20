"""Unit tests for the offline exact solver workflow and certificate validation."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from scripts.solve_recife_exact import (
    ExactSolveResult,
    compute_file_sha256,
    run_exact_workflow,
    solve_instance_exact,
    verify_and_build_certificate,
)
from src.data.models import CVRPInstance
from src.data.recife_loader import load_recife
from src.solver.decoder import total_distance


def _create_recife_fixture(
    tmp_path: Path, *, optimal_value: float | None = None
) -> Path:
    payload: dict = {
        "name": "Recife-Exact-Fixture",
        "capacity": 100,
        "depot": 0,
        "nodes": [
            {
                "id": "DEPOT",
                "name": "CAF",
                "type": "DEPOT",
                "lat": -8.06,
                "lon": -34.92,
                "demand": 0,
            },
            {
                "id": "U1",
                "name": "UBS 1",
                "type": "UBS",
                "lat": -8.05,
                "lon": -34.88,
                "demand": 60,
            },
            {
                "id": "U2",
                "name": "UBS 2",
                "type": "UBS",
                "lat": -8.04,
                "lon": -34.90,
                "demand": 50,
            },
        ],
    }
    if optimal_value is not None:
        payload["optimal_value"] = optimal_value
    (tmp_path / "recife_ubs.json").write_text(json.dumps(payload), encoding="utf-8")

    # Asymmetric distance matrix; optimal 2-route distance: (0->1->0) + (0->2->0) = (2+3) + (4+1) = 10.0
    dist_matrix = np.array(
        [
            [0.0, 2.0, 4.0],
            [3.0, 0.0, 5.0],
            [1.0, 6.0, 0.0],
        ],
        dtype=np.float64,
    )
    np.save(tmp_path / "distance_matrix_road.npy", dist_matrix)
    return tmp_path


def test_verify_and_build_certificate_accepts_valid_optimal() -> None:
    inst = CVRPInstance(
        name="toy-asym",
        distance_matrix=np.array(
            [
                [0.0, 2.0, 4.0],
                [3.0, 0.0, 5.0],
                [1.0, 6.0, 0.0],
            ]
        ),
        demands=np.array([0, 60, 50]),
        capacity=100,
    )
    routes = [[1], [2]]
    expected_dist = total_distance(routes, inst.distance_matrix, inst.depot)
    res = ExactSolveResult(
        status="optimal",
        optimal_proven=True,
        objective=expected_dist,
        best_lb=expected_dist,
        routes=routes,
        runtime_seconds=0.123,
        solver="MockExact",
        solver_version="1.0.0",
    )

    opt, cert = verify_and_build_certificate(inst, res, "abc123")
    assert opt == pytest.approx(10.0)
    assert cert["status"] == "optimal"
    assert cert["distance"] == pytest.approx(10.0)
    assert cert["num_vehicles"] == 2
    assert cert["routes"] == [[1], [2]]
    assert cert["distance_matrix_sha256"] == "abc123"


def test_verify_and_build_certificate_rejects_distance_mismatch() -> None:
    inst = CVRPInstance(
        name="toy-asym",
        distance_matrix=np.array(
            [
                [0.0, 2.0, 4.0],
                [3.0, 0.0, 5.0],
                [1.0, 6.0, 0.0],
            ]
        ),
        demands=np.array([0, 60, 50]),
        capacity=100,
    )
    res = ExactSolveResult(
        status="optimal",
        optimal_proven=True,
        objective=9.5,
        best_lb=9.5,
        routes=[[1], [2]],
        runtime_seconds=0.1,
        solver="MockExact",
        solver_version="1.0.0",
    )
    with pytest.raises(ValueError, match="Distance mismatch"):
        verify_and_build_certificate(inst, res, "abc123")


def test_verify_and_build_certificate_rejects_nonzero_dual_gap() -> None:
    inst = CVRPInstance(
        name="toy-asym",
        distance_matrix=np.array(
            [
                [0.0, 2.0, 4.0],
                [3.0, 0.0, 5.0],
                [1.0, 6.0, 0.0],
            ]
        ),
        demands=np.array([0, 60, 50]),
        capacity=100,
    )
    res = ExactSolveResult(
        status="optimal",
        optimal_proven=True,
        objective=10.0,
        best_lb=9.5,
        routes=[[1], [2]],
        runtime_seconds=0.1,
        solver="MockExact",
        solver_version="1.0.0",
    )
    with pytest.raises(ValueError, match="Non-zero dual/primal gap"):
        verify_and_build_certificate(inst, res, "abc123")


def test_self_check_passing_proceeds_to_recife(tmp_path: Path) -> None:
    data_dir = _create_recife_fixture(tmp_path)
    calls: list[str] = []

    def fake_solver(instance: CVRPInstance, **_: object) -> ExactSolveResult:
        calls.append(instance.name)
        if instance.name == "A-n32-k5":
            # Build valid partition of 1..31 into 5 capacity-feasible routes
            # and mock objective/lb at 784.0; instead use exact A-n32-k5 optimal routes
            # or verify self-check via total_distance. Let's construct valid A-n32-k5
            # routes? Easier: use actual optimal A-n32-k5 routes so total_distance == 784.0.
            routes = [
                [21, 31, 19, 17, 13, 7, 26],
                [12, 1, 16, 30],
                [27, 24],
                [29, 18, 8, 9, 22, 15, 10, 25, 5, 20],
                [14, 28, 11, 4, 23, 3, 2, 6],
            ]
            dist = total_distance(routes, instance.distance_matrix, instance.depot)
            return ExactSolveResult(
                status="optimal",
                optimal_proven=True,
                objective=dist,
                best_lb=dist,
                routes=routes,
                runtime_seconds=0.05,
                solver="MockExact",
                solver_version="1.0.0",
            )
        routes = [[1], [2]]
        dist = total_distance(routes, instance.distance_matrix, instance.depot)
        return ExactSolveResult(
            status="optimal",
            optimal_proven=True,
            objective=dist,
            best_lb=dist,
            routes=routes,
            runtime_seconds=0.05,
            solver="MockExact",
            solver_version="1.0.0",
        )

    rc = run_exact_workflow(
        data_dir=data_dir,
        skip_self_check=False,
        dry_run=True,
        solver_fn=fake_solver,
    )
    assert rc == 0
    assert calls == ["A-n32-k5", "Recife-Exact-Fixture-road"]


def test_self_check_mismatch_aborts_without_modifying_recife_json(
    tmp_path: Path,
) -> None:
    data_dir = _create_recife_fixture(tmp_path, optimal_value=10.0)
    json_path = data_dir / "recife_ubs.json"
    before = json_path.read_text(encoding="utf-8")
    calls: list[str] = []

    def fake_bad_self_check_solver(
        instance: CVRPInstance, **_: object
    ) -> ExactSolveResult:
        calls.append(instance.name)
        # Capacity-feasible routes for A-n32-k5 whose distance != 784.0
        routes = [[c] for c in instance.customers]
        dist = total_distance(routes, instance.distance_matrix, instance.depot)
        return ExactSolveResult(
            status="optimal",
            optimal_proven=True,
            objective=dist,
            best_lb=dist,
            routes=routes,
            runtime_seconds=0.05,
            solver="MockExact",
            solver_version="1.0.0",
        )

    rc = run_exact_workflow(
        data_dir=data_dir,
        skip_self_check=False,
        dry_run=False,
        solver_fn=fake_bad_self_check_solver,
    )
    assert rc == 1
    assert calls == ["A-n32-k5"]
    assert json_path.read_text(encoding="utf-8") == before


def test_dry_run_does_not_modify_recife_json(tmp_path: Path) -> None:
    data_dir = _create_recife_fixture(tmp_path)
    json_path = data_dir / "recife_ubs.json"
    before = json_path.read_text(encoding="utf-8")

    def fake_solver(instance: CVRPInstance, **_: object) -> ExactSolveResult:
        routes = [[1], [2]]
        dist = total_distance(routes, instance.distance_matrix, instance.depot)
        return ExactSolveResult(
            status="optimal",
            optimal_proven=True,
            objective=dist,
            best_lb=dist,
            routes=routes,
            runtime_seconds=0.05,
            solver="MockExact",
            solver_version="1.0.0",
        )

    rc = run_exact_workflow(
        data_dir=data_dir,
        skip_self_check=True,
        dry_run=True,
        solver_fn=fake_solver,
    )
    assert rc == 0
    assert json_path.read_text(encoding="utf-8") == before


def test_unproven_solve_refuses_to_write_optimal_value(tmp_path: Path) -> None:
    data_dir = _create_recife_fixture(tmp_path, optimal_value=10.0)
    json_path = data_dir / "recife_ubs.json"
    before = json_path.read_text(encoding="utf-8")

    def fake_unproven_solver(instance: CVRPInstance, **_: object) -> ExactSolveResult:
        return ExactSolveResult(
            status="better_sol_found",
            optimal_proven=False,
            objective=11.0,
            best_lb=9.0,
            routes=[[1], [2]],
            runtime_seconds=1800.0,
            solver="MockExact",
            solver_version="1.0.0",
        )

    rc = run_exact_workflow(
        data_dir=data_dir,
        skip_self_check=True,
        dry_run=False,
        solver_fn=fake_unproven_solver,
    )
    assert rc == 1
    assert json_path.read_text(encoding="utf-8") == before


def test_certified_solve_persists_optimal_value_and_sha256(tmp_path: Path) -> None:
    data_dir = _create_recife_fixture(tmp_path)
    expected_sha = compute_file_sha256(data_dir / "distance_matrix_road.npy")

    def fake_solver(instance: CVRPInstance, **_: object) -> ExactSolveResult:
        routes = [[1], [2]]
        dist = total_distance(routes, instance.distance_matrix, instance.depot)
        return ExactSolveResult(
            status="optimal",
            optimal_proven=True,
            objective=dist,
            best_lb=dist,
            routes=routes,
            runtime_seconds=0.05,
            solver="MockExact",
            solver_version="1.0.0",
        )

    rc = run_exact_workflow(
        data_dir=data_dir,
        skip_self_check=True,
        dry_run=False,
        solver_fn=fake_solver,
    )
    assert rc == 0

    payload = json.loads((data_dir / "recife_ubs.json").read_text(encoding="utf-8"))
    assert payload["optimal_value"] == pytest.approx(10.0)
    assert payload["exact_solution"]["status"] == "optimal"
    assert payload["exact_solution"]["distance_matrix_sha256"] == expected_sha
    assert payload["exact_solution"]["routes"] == [[1], [2]]

    loaded = load_recife(data_dir)
    assert loaded.optimal_value == pytest.approx(10.0)


@pytest.mark.skipif(
    importlib.util.find_spec("ortools") is None,
    reason="requires optional `exact` dependency group (ortools)",
)
def test_solve_instance_exact_cpsat_toy_asymmetric() -> None:
    inst = CVRPInstance(
        name="toy-asym-cpsat",
        distance_matrix=np.array(
            [
                [0.0, 2.5, 4.25],
                [3.5, 0.0, 5.0],
                [1.75, 6.0, 0.0],
            ]
        ),
        demands=np.array([0, 60, 50]),
        capacity=100,
    )
    res = solve_instance_exact(inst, time_limit=10.0)
    assert res.optimal_proven is True
    assert res.status == "optimal"
    # Optimal routes: (0->1->0) = 6.0 and (0->2->0) = 6.0 => total 12.0
    assert res.objective == pytest.approx(12.0)
    assert res.best_lb == pytest.approx(12.0)
    opt, cert = verify_and_build_certificate(inst, res, "toysha")
    assert opt == pytest.approx(12.0)
    assert cert["num_vehicles"] == 2
