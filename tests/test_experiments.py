"""Smoke and unit tests for experiment runner, statistics, plots, and Recife map."""

from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pytest

from src.data.cvrplib_loader import load_cvrplib
from src.data.recife_loader import load_recife
from src.experiments.map_recife import _fetch_osrm_route_geometry, generate_recife_map
from src.experiments.plots import plot_comparative_boxplots, plot_convergence_curves
from src.experiments.runner import (
    load_recife_suite,
    run_phase1_ablation,
    run_phase2_comparison,
    select_best_operators,
)
from src.experiments.stats import (
    aggregate_results,
    compare_pure_vs_memetic,
    compute_gap_pct,
)


def test_stats_gap_and_nonparametric_tests() -> None:
    assert np.isclose(compute_gap_pct(862.4, 784.0), 10.0)
    assert compute_gap_pct(500.0, None) is None

    rows = []
    for seed, pure_d, mem_d in [
        (1, 100.0, 80.0),
        (2, 102.0, 82.0),
        (3, 105.0, 81.0),
        (4, 101.0, 79.0),
        (5, 104.0, 83.0),
        (6, 103.0, 80.0),
    ]:
        rows.append(
            {
                "instance": "toy",
                "method": "Pure_GA",
                "crossover": "OX",
                "mutation": "Inversion",
                "seed": seed,
                "distance": pure_d,
                "optimal_value": 80.0,
                "num_vehicles": 3,
                "runtime_sec": 0.1,
            }
        )
        rows.append(
            {
                "instance": "toy",
                "method": "Memetic_GA",
                "crossover": "OX",
                "mutation": "Inversion",
                "seed": seed,
                "distance": mem_d,
                "optimal_value": 80.0,
                "num_vehicles": 3,
                "runtime_sec": 0.2,
            }
        )

    summary = aggregate_results(rows)
    assert len(summary) == 2
    mem_summary = [s for s in summary if s["method"] == "Memetic_GA"][0]
    assert np.isclose(mem_summary["best_distance"], 79.0)
    assert np.isclose(mem_summary["best_gap_pct"], -1.25)

    comp = compare_pure_vs_memetic(rows)
    assert len(comp) == 1
    assert comp[0]["wilcoxon_p"] < 0.05
    assert comp[0]["mann_whitney_p"] < 0.05
    assert comp[0]["significant_005"] is True


def test_smoke_experiments_plots_and_recife_map(tmp_path: Path) -> None:
    inst_cvrp = load_cvrplib("data/cvrplib/A-n32-k5.vrp")
    inst_recife = load_recife("data/recife_ubs")

    p1_rows = run_phase1_ablation(
        [inst_cvrp],
        seeds=[1, 2],
        pop_size=12,
        generations=5,
        output_dir=tmp_path,
    )
    assert len(p1_rows) == 8
    assert (tmp_path / "phase1_ablation.csv").exists()
    best_cx, best_mut = select_best_operators(p1_rows)
    assert best_cx in {"OX", "PMX"}
    assert best_mut in {"Swap", "Inversion"}

    p2_rows, p2_histories = run_phase2_comparison(
        [inst_cvrp, inst_recife],
        seeds=[1, 2],
        crossover=best_cx,
        mutation=best_mut,
        pop_size=12,
        generations=5,
        local_search_rate=0.3,
        output_dir=tmp_path,
    )
    # Per instance: 1 Greedy + 2 Pure GA + 2 Memetic GA = 5 rows -> 10 total
    assert len(p2_rows) == 10
    assert (tmp_path / "phase2_results.csv").exists()
    assert (tmp_path / "phase2_summary.csv").exists()
    assert (tmp_path / "phase2_stats_tests.csv").exists()

    conv_paths = plot_convergence_curves(p2_histories, tmp_path)
    box_paths = plot_comparative_boxplots(p2_rows, tmp_path)
    assert len(conv_paths) == 2 and all(p.exists() for p in conv_paths)
    assert len(box_paths) == 2 and all(p.exists() for p in box_paths)

    best_sols = json.loads((tmp_path / "best_solutions.json").read_text(encoding="utf-8"))
    recife_routes = best_sols[inst_recife.name]["Memetic_GA"]["routes"]
    map_path = generate_recife_map(
        inst_recife, recife_routes, tmp_path / "recife_map.html", use_osrm=False
    )
    assert map_path.exists()
    assert map_path.stat().st_size > 1000


def test_fetch_osrm_route_geometry_converts_lonlat_and_handles_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import requests as req_lib

    class _FakeResponse:
        def __init__(self, payload: dict, status_error: Exception | None = None) -> None:
            self._payload = payload
            self._status_error = status_error

        def raise_for_status(self) -> None:
            if self._status_error is not None:
                raise self._status_error

        def json(self) -> dict:
            return self._payload

    captured: dict = {}

    def _fake_get_ok(url: str, params: dict, timeout: float) -> _FakeResponse:
        captured["url"] = url
        captured["params"] = params
        captured["timeout"] = timeout
        return _FakeResponse(
            {
                "code": "Ok",
                "routes": [
                    {
                        "geometry": {
                            "type": "LineString",
                            "coordinates": [
                                [-34.9225, -8.0598],
                                [-34.9150, -8.0550],
                                [-34.9100, -8.0500],
                            ],
                        }
                    }
                ],
            }
        )

    monkeypatch.setattr("src.experiments.map_recife.requests.get", _fake_get_ok)
    coords = _fetch_osrm_route_geometry([[-8.0598, -34.9225], [-8.0500, -34.9100]])
    assert coords == [
        [-8.0598, -34.9225],
        [-8.0550, -34.9150],
        [-8.0500, -34.9100],
    ]
    assert "-34.922500,-8.059800;-34.910000,-8.050000" in captured["url"]
    assert captured["params"] == {"overview": "full", "geometries": "geojson"}

    # Timeout / network error -> None
    def _fake_get_timeout(url: str, params: dict, timeout: float) -> _FakeResponse:
        raise req_lib.Timeout("timed out")

    monkeypatch.setattr("src.experiments.map_recife.requests.get", _fake_get_timeout)
    assert _fetch_osrm_route_geometry([[-8.0598, -34.9225], [-8.0500, -34.9100]]) is None

    # Non-Ok status -> None
    def _fake_get_non_ok(url: str, params: dict, timeout: float) -> _FakeResponse:
        return _FakeResponse({"code": "NoRoute", "routes": []})

    monkeypatch.setattr("src.experiments.map_recife.requests.get", _fake_get_non_ok)
    assert _fetch_osrm_route_geometry([[-8.0598, -34.9225], [-8.0500, -34.9100]]) is None

    # HTTP error -> None
    def _fake_get_http_err(url: str, params: dict, timeout: float) -> _FakeResponse:
        return _FakeResponse({}, status_error=req_lib.HTTPError("503"))

    monkeypatch.setattr("src.experiments.map_recife.requests.get", _fake_get_http_err)
    assert _fetch_osrm_route_geometry([[-8.0598, -34.9225], [-8.0500, -34.9100]]) is None


def test_generate_recife_map_osrm_and_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import requests as req_lib

    inst_recife = load_recife("data/recife_ubs")
    routes = [[1, 2]]

    # 1. Mocked OSRM road geometry includes intermediate street waypoints
    intermediate_lat, intermediate_lon = -8.057123, -34.918456

    class _FakeResp:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            depot_lat, depot_lon = inst_recife.latlon[0]
            stop1_lat, stop1_lon = inst_recife.latlon[1]
            stop2_lat, stop2_lon = inst_recife.latlon[2]
            return {
                "code": "Ok",
                "routes": [
                    {
                        "geometry": {
                            "type": "LineString",
                            "coordinates": [
                                [float(depot_lon), float(depot_lat)],
                                [intermediate_lon, intermediate_lat],
                                [float(stop1_lon), float(stop1_lat)],
                                [float(stop2_lon), float(stop2_lat)],
                                [float(depot_lon), float(depot_lat)],
                            ],
                        }
                    }
                ],
            }

    monkeypatch.setattr(
        "src.experiments.map_recife.requests.get",
        lambda url, params, timeout: _FakeResp(),
    )
    osrm_map = generate_recife_map(inst_recife, routes, tmp_path / "osrm.html", use_osrm=True)
    osrm_html = osrm_map.read_text(encoding="utf-8")
    assert f"[{intermediate_lat}, {intermediate_lon}]" in osrm_html

    # 2. Network failure falls back to straight-line stop coordinates
    def _raise_err(url: str, params: dict, timeout: float) -> _FakeResp:
        raise req_lib.ConnectionError("offline")

    monkeypatch.setattr("src.experiments.map_recife.requests.get", _raise_err)
    fallback_map = generate_recife_map(
        inst_recife, routes, tmp_path / "fallback.html", use_osrm=True
    )
    fallback_html = fallback_map.read_text(encoding="utf-8")
    assert f"[{intermediate_lat}, {intermediate_lon}]" not in fallback_html
    assert "L.polyline(" in fallback_html

    # 3. use_osrm=False skips OSRM calls completely
    called = False

    def _should_not_call(url: str, params: dict, timeout: float) -> _FakeResp:
        nonlocal called
        called = True
        return _FakeResp()

    monkeypatch.setattr("src.experiments.map_recife.requests.get", _should_not_call)
    offline_map = generate_recife_map(
        inst_recife, routes, tmp_path / "offline.html", use_osrm=False
    )
    assert not called
    assert offline_map.exists()
    assert "L.polyline(" in offline_map.read_text(encoding="utf-8")


def test_load_recife_suite_road_only() -> None:
    suite = load_recife_suite("data/recife_ubs")
    assert len(suite) == 1
    assert suite[0].name == "Recife-UBS-40-road"
    assert suite[0].is_symmetric is False
