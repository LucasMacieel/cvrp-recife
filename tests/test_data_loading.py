"""Unit tests for CVRPInstance and data loaders."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from src.data.cvrplib_loader import load_cvrplib
from src.data.models import CVRPInstance
from src.data.recife_loader import load_recife


def _valid_instance(
    *,
    name: str = "toy-3",
    distance_matrix: np.ndarray | None = None,
    demands: np.ndarray | None = None,
    capacity: int = 10,
    depot: int = 0,
) -> CVRPInstance:
    return CVRPInstance(
        name=name,
        distance_matrix=(
            distance_matrix
            if distance_matrix is not None
            else np.array(
                [
                    [0.0, 2.0, 3.0],
                    [2.0, 0.0, 4.0],
                    [3.0, 4.0, 0.0],
                ]
            )
        ),
        demands=demands if demands is not None else np.array([0, 5, 7]),
        capacity=capacity,
        depot=depot,
    )


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
        ("A-n60-k9.vrp", 60, 100, 1354.0),
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
        "NAME : bad\n"
        "TYPE : CVRP\n"
        "DIMENSION : 2\n"
        "EDGE_WEIGHT_TYPE : EUC_2D\n"
        "CAPACITY : 10\n"
        "NODE_COORD_SECTION\n"
        "1 0 0\n"
        "2 3 4\n"
        "DEMAND_SECTION\n"
        "1 0\n"
        "2 15\n"
        "DEPOT_SECTION\n"
        "1\n"
        "-1\n"
        "EOF",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="exceed vehicle capacity"):
        load_cvrplib(bad_vrp)


@pytest.mark.parametrize(
    ("comment_line", "expected_opt"),
    [
        ("COMMENT : (Augerat et al, Min no of trucks: 9, Best value: 1408)", None),
        ("COMMENT : (Augerat et al, Min no of trucks: 9, Optimal value: 1354)", 1354.0),
        ("COMMENT : optimal value: 1354", 1354.0),
    ],
)
def test_load_cvrplib_comment_optimal_vs_best_value(
    tmp_path: Path, comment_line: str, expected_opt: float | None
) -> None:
    vrp = tmp_path / "comment_test.vrp"
    vrp.write_text(
        "NAME : comment_test\n"
        f"{comment_line}\n"
        "TYPE : CVRP\n"
        "DIMENSION : 2\n"
        "EDGE_WEIGHT_TYPE : EUC_2D\n"
        "CAPACITY : 10\n"
        "NODE_COORD_SECTION\n"
        "1 0 0\n"
        "2 3 4\n"
        "DEMAND_SECTION\n"
        "1 0\n"
        "2 5\n"
        "DEPOT_SECTION\n"
        "1\n"
        "-1\n"
        "EOF",
        encoding="utf-8",
    )
    inst = load_cvrplib(vrp)
    assert inst.optimal_value == expected_opt


def test_load_recife_road_only() -> None:
    import json
    from scripts.prepare_recife_data import extract_us_code

    road = load_recife("data/recife_ubs")

    assert road.name == "Recife-UBS-40-road"
    assert road.num_nodes == 41
    assert road.num_customers == 40
    assert road.capacity == 100
    assert road.depot == 0
    assert road.is_symmetric is False
    assert road.latlon is not None and road.latlon.shape == (41, 2)
    assert road.node_names is not None and len(road.node_names) == 41
    assert road.optimal_value == pytest.approx(173.6154)

    payload = json.loads(
        Path("data/recife_ubs/recife_ubs.json").read_text(encoding="utf-8")
    )
    nodes = payload["nodes"]
    node_ids = [n["id"] for n in nodes]
    assert len(node_ids) == 41
    assert len(set(node_ids)) == 41
    us_codes = [
        code
        for n in nodes[1:]
        if (code := extract_us_code(n.get("name", ""))) is not None
    ]
    assert len(us_codes) == len(set(us_codes))


def test_load_recife_missing_road_matrix_raises(tmp_path: Path) -> None:
    src_json = Path("data/recife_ubs/recife_ubs.json").read_text(encoding="utf-8")
    (tmp_path / "recife_ubs.json").write_text(src_json, encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="road distance matrix"):
        load_recife(tmp_path)


def test_load_recife_enriched_demand_metadata_offline(tmp_path: Path) -> None:
    import json

    enriched = {
        "name": "Recife-Enriched-Test",
        "capacity": 100,
        "depot": 0,
        "distance_unit": "km",
        "source": "Test fixture",
        "demand_metadata": {
            "method": "stockout_count_minmax",
            "d_min": 10,
            "d_max": 40,
            "raw_min": 80,
            "raw_max": 200,
            "match_summary": {
                "us_code": 1,
                "name_bairro": 0,
                "type_median_fallback": 1,
                "global_median_fallback": 0,
            },
        },
        "nodes": [
            {
                "id": "DEPOT-CAF",
                "name": "CAF Recife",
                "type": "DEPOT",
                "lat": -8.0598,
                "lon": -34.9225,
                "demand": 0,
            },
            {
                "id": "UBS-1",
                "name": "US 101 Unidade A",
                "type": "UBS",
                "lat": -8.05,
                "lon": -34.88,
                "demand": 10,
                "raw_stockouts": 80,
                "total_items": 300,
                "demand_match_method": "us_code",
            },
            {
                "id": "USF-1",
                "name": "US 999 Unidade B",
                "type": "USF",
                "lat": -8.04,
                "lon": -34.90,
                "demand": 40,
                "raw_stockouts": None,
                "total_items": None,
                "demand_match_method": "type_median_fallback",
                "imputed_stockouts": 200.0,
            },
        ],
    }
    (tmp_path / "recife_ubs.json").write_text(json.dumps(enriched), encoding="utf-8")
    road_matrix = np.array(
        [
            [0.0, 5.2, 3.8],
            [5.4, 0.0, 2.7],
            [3.6, 2.9, 0.0],
        ],
        dtype=np.float64,
    )
    np.save(tmp_path / "distance_matrix_road.npy", road_matrix)

    inst = load_recife(tmp_path)
    assert inst.demands.dtype == np.int64
    assert inst.demands[inst.depot] == 0
    assert np.all((inst.demands[1:] >= 1) & (inst.demands[1:] <= inst.capacity))
    assert list(inst.demands) == [0, 10, 40]


def _write_minimal_recife_fixture(
    tmp_path: Path, extra_payload: dict | None = None
) -> None:
    import json

    payload = {
        "name": "Recife-Opt-Test",
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
                "demand": 15,
            },
            {
                "id": "U2",
                "name": "UBS 2",
                "type": "UBS",
                "lat": -8.04,
                "lon": -34.90,
                "demand": 25,
            },
        ],
    }
    if extra_payload:
        payload.update(extra_payload)
    (tmp_path / "recife_ubs.json").write_text(json.dumps(payload), encoding="utf-8")
    road_matrix = np.array(
        [
            [0.0, 5.2, 3.8],
            [5.4, 0.0, 2.7],
            [3.6, 2.9, 0.0],
        ],
        dtype=np.float64,
    )
    np.save(tmp_path / "distance_matrix_road.npy", road_matrix)


def test_load_recife_with_positive_optimal_value(tmp_path: Path) -> None:
    _write_minimal_recife_fixture(tmp_path, {"optimal_value": 12.345})
    inst = load_recife(tmp_path)
    assert inst.optimal_value == pytest.approx(12.345)
    assert isinstance(inst.optimal_value, float)


def test_load_recife_without_optimal_value(tmp_path: Path) -> None:
    _write_minimal_recife_fixture(tmp_path)
    inst_omitted = load_recife(tmp_path)
    assert inst_omitted.optimal_value is None

    _write_minimal_recife_fixture(tmp_path, {"optimal_value": None})
    inst_null = load_recife(tmp_path)
    assert inst_null.optimal_value is None


@pytest.mark.parametrize("bad_optimal", [0, 0.0, -10.5])
def test_load_recife_rejects_non_positive_optimal_value(
    tmp_path: Path, bad_optimal: float
) -> None:
    _write_minimal_recife_fixture(tmp_path, {"optimal_value": bad_optimal})
    with pytest.raises(ValueError, match="optimal_value must be positive"):
        load_recife(tmp_path)


def test_load_recife_rejects_duplicate_node_ids(tmp_path: Path) -> None:
    _write_minimal_recife_fixture(
        tmp_path,
        {
            "nodes": [
                {
                    "id": "DEPOT-CAF",
                    "name": "CAF",
                    "type": "DEPOT",
                    "lat": -8.06,
                    "lon": -34.92,
                    "demand": 0,
                },
                {
                    "id": "USF-9999999",
                    "name": "USF 1",
                    "type": "USF",
                    "lat": -8.05,
                    "lon": -34.88,
                    "demand": 15,
                },
                {
                    "id": "USF-9999999",
                    "name": "USF 2",
                    "type": "USF",
                    "lat": -8.04,
                    "lon": -34.90,
                    "demand": 25,
                },
            ]
        },
    )
    with pytest.raises(ValueError, match="Duplicate node id.*USF-9999999"):
        load_recife(tmp_path)
