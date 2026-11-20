"""Unit and CLI tests for Optuna hyperparameter optimization (src/experiments/hpo.py)."""

from __future__ import annotations

import csv
import json
import subprocess
from io import StringIO
from pathlib import Path

import numpy as np
import pytest
from rich.console import Console

from src.data.cvrplib_loader import load_cvrplib
from src.data.models import CVRPInstance
from src.experiments.hpo import (
    METHOD_MEMETIC,
    METHOD_PURE,
    _resolve_tuning_instances,
    compute_greedy_baselines,
    evaluate_ga_config,
    load_tuned_configs,
    optimize_ga,
    run_hpo_suite,
)
from src.experiments.hpo import (
    main as hpo_main,
)
from src.experiments.progress import (
    build_hpo_summary_table,
    format_hpo_detail,
    render_hpo_summary,
)
from src.solver.genetic import GAConfig, solve_genetic
from src.solver.greedy import solve_greedy
from src.solver.operators import CROSSOVER_OPERATORS, MUTATION_OPERATORS


def _make_toy_instance(*, optimal_value: float | None = 20.0) -> CVRPInstance:
    coords = np.array(
        [
            [0.0, 0.0],
            [1.0, 0.0],
            [2.0, 0.0],
            [2.0, 1.0],
            [1.0, 1.0],
            [0.0, 1.0],
        ],
        dtype=np.float64,
    )
    diff = coords[:, None, :] - coords[None, :, :]
    dist = np.hypot(diff[:, :, 0], diff[:, :, 1])
    demands = np.array([0, 2, 2, 2, 2, 2], dtype=np.int64)
    return CVRPInstance(
        name="toy-hpo",
        distance_matrix=dist,
        demands=demands,
        capacity=6,
        coords=coords,
        optimal_value=optimal_value,
    )


def test_evaluate_ga_config_with_and_without_optimal_value() -> None:
    inst_opt = _make_toy_instance(optimal_value=10.0)
    cfg = GAConfig(pop_size=20, generations=5, memetic=False, seed=1)
    expected_dist = solve_genetic(inst_opt, cfg).distance
    expected_gap = ((expected_dist - 10.0) / 10.0) * 100.0
    score_opt = evaluate_ga_config(cfg, [inst_opt], [1])
    assert np.isclose(score_opt, expected_gap)

    inst_no_opt = _make_toy_instance(optimal_value=None)
    greedy_dist = solve_greedy(inst_no_opt).distance
    baselines = compute_greedy_baselines([inst_no_opt])
    assert np.isclose(baselines[inst_no_opt.name], greedy_dist)

    expected_greedy_gap = ((expected_dist - greedy_dist) / greedy_dist) * 100.0
    score_no_opt = evaluate_ga_config(cfg, [inst_no_opt], [1], baselines)
    assert np.isclose(score_no_opt, expected_greedy_gap)


def test_optimize_ga_bounds_and_determinism() -> None:
    inst = load_cvrplib("data/cvrplib/A-n32-k5.vrp")
    res1, trials1 = optimize_ga(
        METHOD_PURE,
        [inst],
        [1],
        n_trials=3,
        generations=4,
        hpo_seed=123,
        show_progress=False,
    )
    res2, trials2 = optimize_ga(
        METHOD_PURE,
        [inst],
        [1],
        n_trials=3,
        generations=4,
        hpo_seed=123,
        show_progress=False,
    )

    assert res1["best_objective"] == res2["best_objective"]
    assert res1["best_trial_number"] == res2["best_trial_number"]
    assert res1["config"] == res2["config"]
    assert [t["objective"] for t in trials1] == [t["objective"] for t in trials2]

    for row in trials1:
        assert row["crossover"] in CROSSOVER_OPERATORS
        assert row["mutation"] in MUTATION_OPERATORS
        assert 30 <= row["pop_size"] <= 120
        assert 0.60 <= row["crossover_rate"] <= 0.98
        assert 0.05 <= row["mutation_rate"] <= 0.50
        assert 2 <= row["tournament_k"] <= 6
        assert 1 <= row["elite_size"] <= 6
        assert row["elite_size"] < row["pop_size"]
        assert row["tournament_k"] <= row["pop_size"]


def test_run_hpo_suite_artifacts_and_round_trip(tmp_path: Path) -> None:
    inst = _make_toy_instance(optimal_value=6.0)
    out_dir = tmp_path / "hpo_out"
    results = run_hpo_suite(
        [inst],
        [1, 2],
        methods=(METHOD_PURE, METHOD_MEMETIC),
        n_trials=2,
        generations=3,
        hpo_seed=42,
        output_dir=out_dir,
        show_progress=False,
    )

    json_path = out_dir / "hpo_best_configs.json"
    pure_csv = out_dir / "hpo_trials_pure_ga.csv"
    mem_csv = out_dir / "hpo_trials_memetic_ga.csv"
    assert json_path.is_file()
    assert pure_csv.is_file()
    assert mem_csv.is_file()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["metadata"]["instances"] == ["toy-hpo"]
    assert payload["metadata"]["seeds"] == [1, 2]
    assert payload["metadata"]["n_trials"] == 2
    assert payload["metadata"]["generations"] == 3
    assert payload["metadata"]["hpo_seed"] == 42
    assert METHOD_PURE in payload
    assert METHOD_MEMETIC in payload

    loaded = load_tuned_configs(json_path, require_both=True)
    assert loaded[METHOD_PURE].memetic is False
    assert loaded[METHOD_MEMETIC].memetic is True
    assert loaded[METHOD_MEMETIC].local_search_rate == pytest.approx(
        results[METHOD_MEMETIC]["config"]["local_search_rate"]
    )

    with pure_csv.open("r", encoding="utf-8") as fh:
        pure_rows = list(csv.DictReader(fh))
    assert len(pure_rows) == 2
    assert {
        "trial_number",
        "state",
        "objective",
        "duration_sec",
        "pop_size",
        "crossover",
    }.issubset(pure_rows[0].keys())

    with mem_csv.open("r", encoding="utf-8") as fh:
        mem_rows = list(csv.DictReader(fh))
    assert len(mem_rows) == 2
    assert {"local_search_rate", "local_search_max_passes"}.issubset(mem_rows[0].keys())


def test_load_tuned_configs_validation_errors(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.json"
    with pytest.raises(FileNotFoundError):
        load_tuned_configs(missing_path)

    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{not-json", encoding="utf-8")
    with pytest.raises(ValueError):
        load_tuned_configs(bad_json)

    invalid_cfg = tmp_path / "invalid_bounds.json"
    invalid_cfg.write_text(
        json.dumps(
            {
                "Pure_GA": {
                    "best_objective": 1.0,
                    "best_trial_number": 0,
                    "config": {
                        "pop_size": 4,
                        "crossover_rate": 0.8,
                        "mutation_rate": 0.2,
                        "tournament_k": 3,
                        "elite_size": 4,  # invalid: elite_size >= pop_size
                        "crossover": "OX",
                        "mutation": "Swap",
                        "memetic": False,
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="elite_size"):
        load_tuned_configs(invalid_cfg)

    with pytest.raises(ValueError, match="both Pure_GA and Memetic_GA"):
        only_pure = tmp_path / "only_pure.json"
        only_pure.write_text(
            json.dumps(
                {
                    "Pure_GA": {
                        "best_objective": 1.0,
                        "best_trial_number": 0,
                        "config": {
                            "pop_size": 30,
                            "crossover_rate": 0.8,
                            "mutation_rate": 0.2,
                            "tournament_k": 3,
                            "elite_size": 2,
                            "crossover": "OX",
                            "mutation": "Swap",
                            "memetic": False,
                        },
                    }
                }
            ),
            encoding="utf-8",
        )
        load_tuned_configs(only_pure, require_both=True)


def test_hpo_cli_single_method_and_no_progress_parity(tmp_path: Path) -> None:
    out_progress = tmp_path / "with_progress"
    out_silent = tmp_path / "no_progress"

    hpo_main(
        [
            "--method",
            "pure",
            "--trials",
            "2",
            "--seeds",
            "1",
            "--generations",
            "3",
            "--hpo-seed",
            "7",
            "--instances",
            "A-n32-k5",
            "--output-dir",
            str(out_progress),
        ]
    )
    hpo_main(
        [
            "--method",
            "pure",
            "--trials",
            "2",
            "--seeds",
            "1",
            "--generations",
            "3",
            "--hpo-seed",
            "7",
            "--instances",
            "A-n32-k5",
            "--output-dir",
            str(out_silent),
            "--no-progress",
        ]
    )

    assert (out_silent / "hpo_trials_pure_ga.csv").is_file()
    assert not (out_silent / "hpo_trials_memetic_ga.csv").exists()

    json_prog = json.loads(
        (out_progress / "hpo_best_configs.json").read_text(encoding="utf-8")
    )
    json_sil = json.loads(
        (out_silent / "hpo_best_configs.json").read_text(encoding="utf-8")
    )
    assert METHOD_PURE in json_sil
    assert METHOD_MEMETIC not in json_sil
    assert json_prog["Pure_GA"] == json_sil["Pure_GA"]
    assert json_prog["metadata"] == json_sil["metadata"]

    buf_off = StringIO()
    console_off = Console(file=buf_off, force_terminal=False, width=120)
    inst = load_cvrplib("data/cvrplib/A-n32-k5.vrp")
    run_hpo_suite(
        [inst],
        [1],
        methods=(METHOD_PURE,),
        n_trials=1,
        generations=2,
        hpo_seed=7,
        output_dir=tmp_path / "suite_silent",
        show_progress=False,
        console=console_off,
    )
    assert buf_off.getvalue() == ""


def test_hpo_progress_formatting_and_cli_help() -> None:
    detail = format_hpo_detail(
        "Pure_GA", 2, 10, last_objective=5.12, best_objective=4.5
    )
    assert "Pure_GA" in detail
    assert "trial 2/10" in detail
    assert "last=5.12%" in detail
    assert "best=4.50%" in detail

    sample_results = {
        "Pure_GA": {
            "best_objective": 5.5,
            "best_trial_number": 1,
            "config": {
                "pop_size": 50,
                "crossover_rate": 0.85,
                "mutation_rate": 0.2,
                "tournament_k": 3,
                "elite_size": 2,
                "crossover": "OX",
                "mutation": "Inversion",
                "memetic": False,
            },
        }
    }
    table = build_hpo_summary_table(sample_results)
    assert table.title == "Hyperparameter Optimization Summary"

    buf = StringIO()
    console = Console(file=buf, force_terminal=False, width=120)
    render_hpo_summary(console, sample_results)
    output = buf.getvalue()
    assert "Pure_GA" in output
    assert "OX+Inversion" in output

    proc = subprocess.run(
        ["uv", "run", "-m", "src.experiments.hpo", "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "--method" in proc.stdout
    assert "--no-progress" in proc.stdout
    assert "A-n32-k5 A-n45-k6 A-n60-k9" in proc.stdout
    assert "A-n80-k10" not in proc.stdout


def test_resolve_default_tuning_instances() -> None:
    instances = _resolve_tuning_instances(None)
    names = [inst.name for inst in instances]
    assert names == ["A-n32-k5", "A-n45-k6", "A-n60-k9"]
    assert "A-n80-k10" not in names
    assert "Recife-UBS-40-road" not in names
