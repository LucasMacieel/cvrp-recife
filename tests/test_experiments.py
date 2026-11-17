"""Smoke and unit tests for experiment runner, statistics, plots, and Recife map."""

from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pytest

from src.data.cvrplib_loader import load_cvrplib
from src.data.recife_loader import load_recife
from src.experiments.map_recife import generate_recife_map
from src.experiments.plots import plot_comparative_boxplots, plot_convergence_curves
from src.experiments.runner import (
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
    inst_recife = load_recife("data/recife_ubs", mode="road")

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
    map_path = generate_recife_map(inst_recife, recife_routes, tmp_path / "recife_map.html")
    assert map_path.exists()
    assert map_path.stat().st_size > 1000
