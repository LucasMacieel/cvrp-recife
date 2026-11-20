"""Smoke and unit tests for experiment runner, statistics, plots, and Recife map."""

from __future__ import annotations

import csv
import json
from dataclasses import replace
from io import StringIO
from pathlib import Path

import numpy as np
import pytest
from rich.console import Console

from src.data.cvrplib_loader import load_cvrplib
from src.data.recife_loader import load_recife
from src.experiments.map_recife import _fetch_osrm_route_geometry, generate_recife_map
from src.experiments.plots import (
    plot_best_solution_routes,
    plot_comparative_boxplots,
    plot_convergence_curves,
)
from src.experiments.progress import (
    create_experiment_progress,
    format_run_detail,
    render_phase2_summary,
)
from src.experiments.runner import (
    build_arg_parser,
    load_cvrplib_suite,
    load_recife_suite,
    run_phase2_comparison,
    run_post_processing,
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
    mem_summary = next(s for s in summary if s["method"] == "Memetic_GA")
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

    p2_rows, p2_histories = run_phase2_comparison(
        [inst_cvrp, inst_recife],
        seeds=[1, 2],
        crossover="OX",
        mutation="Inversion",
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

    best_sols = json.loads(
        (tmp_path / "best_solutions.json").read_text(encoding="utf-8")
    )
    recife_best = best_sols[inst_recife.name]["Memetic_GA"]
    recife_routes = recife_best["routes"]
    recife_dist = float(recife_best["distance"])

    best_plot_path = plot_best_solution_routes(
        inst_recife,
        recife_routes,
        recife_dist,
        tmp_path / f"best_solution_{inst_recife.name}.png",
        use_osrm=False,
    )
    assert best_plot_path.exists()
    assert best_plot_path.stat().st_size > 1000

    cvrp_best = best_sols[inst_cvrp.name]["Memetic_GA"]
    cvrp_plot_path = plot_best_solution_routes(
        inst_cvrp,
        cvrp_best["routes"],
        float(cvrp_best["distance"]),
        tmp_path / f"best_solution_{inst_cvrp.name}.png",
        use_osrm=False,
    )
    assert cvrp_plot_path.exists()
    assert cvrp_plot_path.stat().st_size > 1000

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
        def __init__(
            self, payload: dict, status_error: Exception | None = None
        ) -> None:
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
    assert (
        _fetch_osrm_route_geometry([[-8.0598, -34.9225], [-8.0500, -34.9100]]) is None
    )

    # Non-Ok status -> None
    def _fake_get_non_ok(url: str, params: dict, timeout: float) -> _FakeResponse:
        return _FakeResponse({"code": "NoRoute", "routes": []})

    monkeypatch.setattr("src.experiments.map_recife.requests.get", _fake_get_non_ok)
    assert (
        _fetch_osrm_route_geometry([[-8.0598, -34.9225], [-8.0500, -34.9100]]) is None
    )

    # HTTP error -> None
    def _fake_get_http_err(url: str, params: dict, timeout: float) -> _FakeResponse:
        return _FakeResponse({}, status_error=req_lib.HTTPError("503"))

    monkeypatch.setattr("src.experiments.map_recife.requests.get", _fake_get_http_err)
    assert (
        _fetch_osrm_route_geometry([[-8.0598, -34.9225], [-8.0500, -34.9100]]) is None
    )


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
            assert inst_recife.latlon is not None
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
    osrm_map = generate_recife_map(
        inst_recife, routes, tmp_path / "osrm.html", use_osrm=True
    )
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


def test_load_cvrplib_suite_three_instances() -> None:
    suite = load_cvrplib_suite("data/cvrplib")
    names = [inst.name for inst in suite]
    assert names == ["A-n32-k5", "A-n45-k6", "A-n60-k9"]
    assert "A-n80-k10" not in names


def test_progress_formatting_and_summary_tables() -> None:
    # With optimal_value -> includes gap%
    with_opt = format_run_detail(
        "A-n32-k5",
        "OX+Inversion",
        2,
        10,
        last_distance=862.4,
        best_distance=862.4,
        optimal_value=784.0,
    )
    assert "inst=A-n32-k5" in with_opt
    assert "OX+Inversion" in with_opt
    assert "seed 2/10" in with_opt
    assert "last=862.40" in with_opt
    assert "best=862.40 (gap=10.00%)" in with_opt

    # Without optimal_value -> omits gap%
    without_opt = format_run_detail(
        "Recife-UBS-40-road",
        "Memetic_GA",
        1,
        5,
        last_distance=45123.5,
        best_distance=44000.0,
        optimal_value=None,
    )
    assert "inst=Recife-UBS-40-road" in without_opt
    assert "Memetic_GA" in without_opt
    assert "seed 1/5" in without_opt
    assert "last=45123.50" in without_opt
    assert "best=44000.00" in without_opt
    assert "gap=" not in without_opt

    # Progress bar renders task and detail to captured Console
    buf = StringIO()
    console = Console(file=buf, force_terminal=False, width=160)
    with create_experiment_progress(console=console, disable=False) as progress:
        tid = progress.add_task("Phase 2: Comparison", total=2, detail=with_opt)
        progress.advance(tid, 1)
    rendered_progress = buf.getvalue()
    assert "Phase 2: Comparison" in rendered_progress
    assert "A-n32-k5" in rendered_progress

    # Phase 2 summary table (one with optimal_value, one without)
    p2_rows = [
        {
            "instance": "A-n32-k5",
            "method": "Memetic_GA",
            "crossover": "OX",
            "mutation": "Inversion",
            "seed": 1,
            "distance": 784.0,
            "optimal_value": 784.0,
            "num_vehicles": 5,
            "runtime_sec": 0.25,
        },
        {
            "instance": "Recife-UBS-40-road",
            "method": "Greedy",
            "crossover": "-",
            "mutation": "-",
            "seed": 0,
            "distance": 50000.0,
            "optimal_value": None,
            "num_vehicles": 4,
            "runtime_sec": 0.01,
        },
    ]
    buf2 = StringIO()
    c2 = Console(file=buf2, force_terminal=False, width=160)
    render_phase2_summary(c2, p2_rows)
    out2 = buf2.getvalue()
    assert "Phase 2: Benchmark Comparison Summary" in out2
    assert "A-n32-k5" in out2
    assert "Memetic_GA" in out2
    assert "0.00%" in out2
    assert "Recife-UBS-40-road" in out2
    assert "Greedy" in out2


def test_runner_progress_and_no_progress(tmp_path: Path) -> None:
    inst_cvrp = load_cvrplib("data/cvrplib/A-n32-k5.vrp")
    inst_recife = load_recife("data/recife_ubs")

    on_dir = tmp_path / "with_progress"
    off_dir = tmp_path / "no_progress"

    # Phase 2 with progress enabled vs disabled
    buf2_on = StringIO()
    console2_on = Console(file=buf2_on, force_terminal=False, width=160)
    p2_on, _ = run_phase2_comparison(
        [inst_cvrp, inst_recife],
        seeds=[1, 2],
        crossover="OX",
        mutation="Inversion",
        pop_size=10,
        generations=3,
        output_dir=on_dir,
        show_progress=True,
        console=console2_on,
    )
    p2_out = buf2_on.getvalue()
    assert "Phase 2: Comparison" in p2_out
    assert "A-n32-k5" in p2_out
    assert "Recife-UBS-40-road" in p2_out
    assert "Memetic_GA" in p2_out
    assert "seed 2/2" in p2_out
    assert "Phase 2: Benchmark Comparison Summary" in p2_out

    buf2_off = StringIO()
    console2_off = Console(file=buf2_off, force_terminal=False, width=160)
    p2_off, _ = run_phase2_comparison(
        [inst_cvrp, inst_recife],
        seeds=[1, 2],
        crossover="OX",
        mutation="Inversion",
        pop_size=10,
        generations=3,
        output_dir=off_dir,
        show_progress=False,
        console=console2_off,
    )
    assert buf2_off.getvalue() == ""
    assert len(p2_on) == len(p2_off) == 10
    for fname in [
        "phase2_results.csv",
        "phase2_summary.csv",
        "phase2_stats_tests.csv",
        "phase2_histories.json",
        "best_solutions.json",
    ]:
        assert (on_dir / fname).exists()
        assert (off_dir / fname).exists()
    assert (on_dir / "phase2_histories.json").read_text(encoding="utf-8") == (
        off_dir / "phase2_histories.json"
    ).read_text(encoding="utf-8")


def test_cli_no_progress_flag_and_post_processing_progress(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parser = build_arg_parser()
    default_args = parser.parse_args([])
    assert default_args.no_progress is False
    disabled_args = parser.parse_args(["--no-progress"])
    assert disabled_args.no_progress is True

    inst_recife = load_recife("data/recife_ubs")
    p2_rows, p2_histories = run_phase2_comparison(
        [inst_recife],
        seeds=[1],
        pop_size=10,
        generations=3,
        output_dir=tmp_path,
        show_progress=False,
    )

    # Avoid network calls during map and route-plot generation in unit test
    monkeypatch.setattr(
        "src.experiments.runner.generate_recife_map",
        lambda inst, routes, out_path: (
            out_path.write_text("<html></html>", encoding="utf-8") or out_path
        ),
    )
    monkeypatch.setattr(
        "src.experiments.runner.plot_best_solution_routes",
        lambda inst, routes, dist, out_path: (
            out_path.write_bytes(b"\x89PNG") and out_path
        ),
    )

    buf_on = StringIO()
    console_on = Console(file=buf_on, force_terminal=False, width=160)
    run_post_processing(
        p2_rows,
        p2_histories,
        inst_recife,
        tmp_path,
        show_progress=True,
        console=console_on,
    )
    out_on = buf_on.getvalue()
    assert "Post-processing" in out_on
    assert "4/4" in out_on
    assert "Generating Recife HTML map" in out_on
    assert (tmp_path / f"best_solution_{inst_recife.name}.png").exists()

    buf_off = StringIO()
    console_off = Console(file=buf_off, force_terminal=False, width=160)
    run_post_processing(
        p2_rows,
        p2_histories,
        inst_recife,
        tmp_path,
        show_progress=False,
        console=console_off,
    )
    assert buf_off.getvalue() == ""
    assert (tmp_path / "recife_map.html").exists()
    assert (tmp_path / f"best_solution_{inst_recife.name}.png").exists()


def test_phase2_with_method_specific_tuned_configs(tmp_path: Path) -> None:
    from src.solver.genetic import GAConfig

    inst = load_cvrplib("data/cvrplib/A-n32-k5.vrp")
    pure_cfg = GAConfig(
        pop_size=12,
        generations=999,  # overridden by Phase 2 generations=3
        crossover_rate=0.90,
        mutation_rate=0.25,
        tournament_k=3,
        elite_size=1,
        crossover="PMX",
        mutation="Swap",
        memetic=False,
    )
    mem_cfg = GAConfig(
        pop_size=10,
        generations=999,
        crossover_rate=0.80,
        mutation_rate=0.15,
        tournament_k=2,
        elite_size=1,
        crossover="OX",
        mutation="Inversion",
        memetic=True,
        local_search_rate=0.20,
        local_search_max_passes=5,
    )

    rows, _histories = run_phase2_comparison(
        [inst],
        seeds=[1, 2],
        generations=3,
        pure_ga_config=pure_cfg,
        memetic_ga_config=mem_cfg,
        output_dir=tmp_path,
        show_progress=False,
    )

    pure_rows = [r for r in rows if r["method"] == "Pure_GA"]
    mem_rows = [r for r in rows if r["method"] == "Memetic_GA"]
    assert len(pure_rows) == 2
    assert len(mem_rows) == 2
    assert all(r["crossover"] == "PMX" and r["mutation"] == "Swap" for r in pure_rows)
    assert all(
        r["crossover"] == "OX" and r["mutation"] == "Inversion" for r in mem_rows
    )


def test_runner_cli_tune_and_tuned_config_flags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.experiments.runner import main as runner_main

    parser = build_arg_parser()
    defaults = parser.parse_args([])
    assert defaults.tuned_config is None
    assert defaults.tune is False
    assert defaults.hpo_trials == 30
    assert defaults.hpo_seeds == 3
    assert defaults.hpo_generations == 100
    assert defaults.hpo_seed == 42

    # Removed legacy CLI flags must fail
    for removed_flag in ("--phase1-seeds", "--pop-size", "--ls-rate"):
        with pytest.raises(SystemExit):
            parser.parse_args([removed_flag, "5"])

    # Mutually exclusive flags must fail
    with pytest.raises(SystemExit):
        parser.parse_args(["--tune", "--tuned-config", "some.json"])

    # Missing --tuned-config file must fail before Phase 2
    with pytest.raises(SystemExit):
        runner_main(["--tuned-config", str(tmp_path / "does_not_exist.json")])

    # Invalid/incomplete --tuned-config file must fail before Phase 2
    invalid_cfg_path = tmp_path / "invalid_tuned_config.json"
    invalid_cfg_path.write_text('{"Pure_GA": {"config": {}}}', encoding="utf-8")
    with pytest.raises(SystemExit):
        runner_main(["--tuned-config", str(invalid_cfg_path)])

    # Valid --tuned-config skips inline Phase 1 HPO and passes tuned configs to Phase 2
    cfg_path = tmp_path / "hpo_best_configs.json"
    cfg_path.write_text(
        json.dumps(
            {
                "metadata": {
                    "instances": ["A-n32-k5", "A-n45-k6", "A-n60-k9"],
                    "seeds": [1],
                    "n_trials": 1,
                    "generations": 3,
                    "hpo_seed": 42,
                },
                "Pure_GA": {
                    "best_objective": 10.0,
                    "best_trial_number": 0,
                    "config": {
                        "pop_size": 12,
                        "crossover_rate": 0.85,
                        "mutation_rate": 0.2,
                        "tournament_k": 3,
                        "elite_size": 1,
                        "crossover": "PMX",
                        "mutation": "Swap",
                        "memetic": False,
                    },
                },
                "Memetic_GA": {
                    "best_objective": 2.0,
                    "best_trial_number": 0,
                    "config": {
                        "pop_size": 10,
                        "crossover_rate": 0.8,
                        "mutation_rate": 0.15,
                        "tournament_k": 2,
                        "elite_size": 1,
                        "crossover": "OX",
                        "mutation": "Inversion",
                        "memetic": True,
                        "local_search_rate": 0.2,
                        "local_search_max_passes": 5,
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    inst = load_cvrplib("data/cvrplib/A-n32-k5.vrp")
    recife_stub = replace(inst, name="Recife-UBS-40-road")
    monkeypatch.setattr(
        "src.experiments.runner.load_cvrplib_suite", lambda _: [inst, inst, inst]
    )
    monkeypatch.setattr(
        "src.experiments.runner.load_recife_suite", lambda _: [recife_stub]
    )
    monkeypatch.setattr(
        "src.experiments.runner.run_post_processing", lambda *a, **kw: None
    )

    out_tuned = tmp_path / "out_tuned"
    runner_main(
        [
            "--tuned-config",
            str(cfg_path),
            "--phase2-seeds",
            "1",
            "--generations",
            "2",
            "--output-dir",
            str(out_tuned),
            "--no-progress",
        ]
    )
    assert not (out_tuned / "phase1_ablation.csv").exists()
    assert not (out_tuned / "hpo_best_configs.json").exists()
    assert (out_tuned / "phase2_results.csv").is_file()
    with (out_tuned / "phase2_results.csv").open("r", encoding="utf-8") as fh:
        tuned_rows = list(csv.DictReader(fh))
    pure_tuned_rows = [r for r in tuned_rows if r["method"] == "Pure_GA"]
    mem_tuned_rows = [r for r in tuned_rows if r["method"] == "Memetic_GA"]
    assert pure_tuned_rows and all(
        r["crossover"] == "PMX" and r["mutation"] == "Swap" for r in pure_tuned_rows
    )
    assert mem_tuned_rows and all(
        r["crossover"] == "OX" and r["mutation"] == "Inversion" for r in mem_tuned_rows
    )

    # Default invocation (omitting --tuned-config and --tune) runs inline Phase 1 HPO -> Phase 2
    out_default = tmp_path / "out_default"
    runner_main(
        [
            "--hpo-trials",
            "1",
            "--hpo-seeds",
            "1",
            "--hpo-generations",
            "2",
            "--phase2-seeds",
            "1",
            "--generations",
            "2",
            "--output-dir",
            str(out_default),
            "--no-progress",
        ]
    )
    assert not (out_default / "phase1_ablation.csv").exists()
    assert (out_default / "hpo_best_configs.json").is_file()
    assert (out_default / "hpo_trials_pure_ga.csv").is_file()
    assert (out_default / "hpo_trials_memetic_ga.csv").is_file()
    assert (out_default / "phase2_results.csv").is_file()
    default_hpo_meta = json.loads(
        (out_default / "hpo_best_configs.json").read_text(encoding="utf-8")
    )["metadata"]
    assert "Recife-UBS-40-road" not in default_hpo_meta["instances"]
    with (out_default / "phase2_results.csv").open("r", encoding="utf-8") as fh:
        default_p2_instances = {r["instance"] for r in csv.DictReader(fh)}
    assert "Recife-UBS-40-road" in default_p2_instances

    # --tune alias also runs inline Phase 1 HPO -> Phase 2
    out_inline = tmp_path / "out_inline"
    runner_main(
        [
            "--tune",
            "--hpo-trials",
            "1",
            "--hpo-seeds",
            "1",
            "--hpo-generations",
            "2",
            "--phase2-seeds",
            "1",
            "--generations",
            "2",
            "--output-dir",
            str(out_inline),
            "--no-progress",
        ]
    )
    assert not (out_inline / "phase1_ablation.csv").exists()
    assert (out_inline / "hpo_best_configs.json").is_file()
    assert (out_inline / "phase2_results.csv").is_file()


def test_plot_best_solution_routes_osrm_fallback_and_missing_coords(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    import logging

    import requests as req_lib

    inst_recife = load_recife("data/recife_ubs")
    inst_cvrp = load_cvrplib("data/cvrplib/A-n32-k5.vrp")
    routes = [[1, 2]]
    assert inst_recife.latlon is not None

    # 1. use_osrm=True queries OSRM and renders static PNG
    called = 0

    class _FakeResp:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            assert inst_recife.latlon is not None
            depot_lat, depot_lon = inst_recife.latlon[0]
            s1_lat, s1_lon = inst_recife.latlon[1]
            s2_lat, s2_lon = inst_recife.latlon[2]
            return {
                "code": "Ok",
                "routes": [
                    {
                        "geometry": {
                            "type": "LineString",
                            "coordinates": [
                                [float(depot_lon), float(depot_lat)],
                                [-34.918456, -8.057123],
                                [float(s1_lon), float(s1_lat)],
                                [float(s2_lon), float(s2_lat)],
                                [float(depot_lon), float(depot_lat)],
                            ],
                        }
                    }
                ],
            }

    def _fake_get_ok(url: str, params: dict, timeout: float) -> _FakeResp:
        nonlocal called
        called += 1
        return _FakeResp()

    monkeypatch.setattr("src.experiments.map_recife.requests.get", _fake_get_ok)
    osrm_png = plot_best_solution_routes(
        inst_recife,
        routes,
        12.34,
        tmp_path / "best_osrm.png",
        use_osrm=True,
    )
    assert called == 1
    assert osrm_png.exists()
    assert osrm_png.stat().st_size > 1000

    # 2. OSRM failure logs a warning and falls back to straight-line segments
    def _fake_get_fail(url: str, params: dict, timeout: float) -> _FakeResp:
        raise req_lib.Timeout("timed out")

    monkeypatch.setattr("src.experiments.map_recife.requests.get", _fake_get_fail)
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="src.experiments.map_recife"):
        fallback_png = plot_best_solution_routes(
            inst_recife,
            routes,
            12.34,
            tmp_path / "best_fallback.png",
            use_osrm=True,
        )
    assert fallback_png.exists()
    assert fallback_png.stat().st_size > 1000
    assert any(
        "falling back to straight-line segments" in rec.message
        for rec in caplog.records
    )

    # 3. Missing both latlon and coords raises ValueError
    no_coords_inst = replace(inst_cvrp, coords=None, latlon=None)
    with pytest.raises(ValueError, match="latlon or coords"):
        plot_best_solution_routes(
            no_coords_inst,
            routes,
            100.0,
            tmp_path / "missing_coords.png",
        )
