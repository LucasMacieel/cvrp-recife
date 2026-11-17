"""Unit tests for CVRPInstance and data loaders."""

from __future__ import annotations

from pathlib import Path
import numpy as np
import pytest

from src.data.cvrplib_loader import load_cvrplib
from src.data.models import CVRPInstance
from src.data.recife_loader import compute_haversine_matrix, load_recife


def _valid_instance(**overrides) -> CVRPInstance:
    defaults = dict(
        name="toy-3",
        distance_matrix=np.array(
            [
                [0.0, 2.0, 3.0],
                [2.0, 0.0, 4.0],
                [3.0, 4.0, 0.0],
            ]
        ),
        demands=np.array([0, 5, 7]),
        capacity=10,
        depot=0,
    )
    defaults.update(overrides)
    return CVRPInstance(**defaults)


def test_valid_cvrp_instance_properties() -> None:
    inst = _valid_instance()
    assert inst.num_nodes == 3
    assert inst.num_customers == 2
    assert inst.customers == [1, 2]
    assert inst.is_symmetric is True
    assert inst.capacity == 10


def test_invalid_non_square_matrix() -> None:
    with pytest.raises(ValueError, match="square"):
        _valid_instance(distance_matrix=np.zeros((2, 3)))


def test_invalid_nan_or_negative_distances() -> None:
    bad_nan = np.array([[0.0, np.nan], [1.0, 0.0]])
    with pytest.raises(ValueError, match="NaN"):
        _valid_instance(distance_matrix=bad_nan, demands=np.array([0, 5]))

    bad_neg = np.array([[0.0, -1.0], [1.0, 0.0]])
    with pytest.raises(ValueError, match="negative"):
        _valid_instance(distance_matrix=bad_neg, demands=np.array([0, 5]))


def test_invalid_demands_and_capacity() -> None:
    with pytest.raises(ValueError, match="depot demand"):
        _valid_instance(demands=np.array([1, 5, 5]))

    with pytest.raises(ValueError, match="exceed vehicle capacity"):
        _valid_instance(demands=np.array([0, 11, 5]), capacity=10)

    with pytest.raises(ValueError, match="shape"):
        _valid_instance(demands=np.array([0, 5]))

    with pytest.raises(ValueError, match="at least 2 nodes"):
        _valid_instance(distance_matrix=np.array([[0.0]]), demands=np.array([0]))


@pytest.mark.parametrize(
    ("filename", "expected_n", "expected_cap", "expected_opt"),
    [
        ("A-n32-k5.vrp", 32, 100, 784.0),
        ("A-n45-k6.vrp", 45, 100, 944.0),
        ("A-n60-k9.vrp", 60, 100, 1408.0),
        ("A-n80-k10.vrp", 80, 100, 1764.0),
    ],
)
def test_load_cvrplib_benchmarks(
    filename: str, expected_n: int, expected_cap: int, expected_opt: float
) -> None:
    path = Path("data/cvrplib") / filename
    inst = load_cvrplib(path)
    assert inst.num_nodes == expected_n
    assert inst.num_customers == expected_n - 1
    assert inst.capacity == expected_cap
    assert inst.optimal_value == expected_opt
    assert inst.depot == 0
    assert inst.demands[0] == 0
    assert inst.distance_matrix.shape == (expected_n, expected_n)
    assert inst.is_symmetric is True
    assert np.all(np.diag(inst.distance_matrix) == 0.0)


def test_load_cvrplib_rejects_infeasible_demand(tmp_path: Path) -> None:
    bad_vrp = tmp_path / "bad.vrp"
    bad_vrp.write_text(
        "\n".join(
            [
                "NAME : bad",
                "TYPE : CVRP",
                "DIMENSION : 2",
                "EDGE_WEIGHT_TYPE : EUC_2D",
                "CAPACITY : 10",
                "NODE_COORD_SECTION",
                "1 0 0",
                "2 3 4",
                "DEMAND_SECTION",
                "1 0",
                "2 15",
                "DEPOT_SECTION",
                "1",
                "-1",
                "EOF",
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="exceed vehicle capacity"):
        load_cvrplib(bad_vrp)


def test_load_recife_road_and_haversine() -> None:
    road = load_recife("data/recife_ubs", mode="road")
    hav = load_recife("data/recife_ubs", mode="haversine")

    assert road.num_nodes == 41
    assert road.num_customers == 40
    assert road.capacity == 100
    assert road.depot == 0
    assert road.latlon is not None and road.latlon.shape == (41, 2)
    assert road.node_names is not None and len(road.node_names) == 41

    assert hav.num_nodes == 41
    assert hav.is_symmetric is True
    # Road distances in Recife are generally >= Haversine geodesic distances
    assert float(road.distance_matrix.mean()) >= float(hav.distance_matrix.mean())


def test_load_recife_haversine_fallback_when_road_missing(tmp_path: Path) -> None:
    src_json = Path("data/recife_ubs/recife_ubs.json").read_text(encoding="utf-8")
    (tmp_path / "recife_ubs.json").write_text(src_json, encoding="utf-8")

    fallback = load_recife(tmp_path, mode="road")
    expected = compute_haversine_matrix(fallback.latlon)
    assert np.allclose(fallback.distance_matrix, expected)


def test_load_recife_invalid_mode() -> None:
    with pytest.raises(ValueError, match="Unsupported Recife distance mode"):
        load_recife("data/recife_ubs", mode="invalid")
