"""Automated multi-seed experiment runner for CVRP ablation and benchmarking."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import numpy as np

from src.data.cvrplib_loader import load_cvrplib
from src.data.models import CVRPInstance
from src.data.recife_loader import load_recife
from src.experiments.map_recife import generate_recife_map
from src.experiments.plots import plot_comparative_boxplots, plot_convergence_curves
from src.experiments.stats import (
    aggregate_results,
    compare_pure_vs_memetic,
    compute_gap_pct,
    save_csv,
)
from src.solver.genetic import GAConfig, solve_genetic
from src.solver.greedy import solve_greedy


def load_cvrplib_suite(data_dir: str | Path = "data/cvrplib") -> list[CVRPInstance]:
    """Load the 4 benchmark CVRPLIB instances in increasing size order."""
    base = Path(data_dir)
    names = ["A-n32-k5.vrp", "A-n45-k6.vrp", "A-n60-k9.vrp", "A-n80-k10.vrp"]
    return [load_cvrplib(base / name) for name in names]


def load_recife_suite(data_dir: str | Path = "data/recife_ubs") -> list[CVRPInstance]:
    """Load the Recife/PE road-network (OSRM) instance."""
    return [load_recife(data_dir)]


def _make_row(
    instance: CVRPInstance,
    method: str,
    crossover: str,
    mutation: str,
    seed: int | str,
    distance: float,
    num_vehicles: int,
    runtime_sec: float,
) -> dict:
    return {
        "instance": instance.name,
        "method": method,
        "crossover": crossover,
        "mutation": mutation,
        "seed": seed,
        "distance": round(float(distance), 6),
        "optimal_value": instance.optimal_value,
        "gap_pct": (
            round(gap, 4)
            if (gap := compute_gap_pct(distance, instance.optimal_value)) is not None
            else None
        ),
        "num_vehicles": int(num_vehicles),
        "runtime_sec": round(float(runtime_sec), 6),
    }


def run_phase1_ablation(
    instances: list[CVRPInstance],
    seeds: list[int],
    *,
    pop_size: int = 60,
    generations: int = 150,
    output_dir: str | Path = "results",
) -> list[dict]:
    """Phase 1: Ablation over (OX, PMX) x (Swap, Inversion) on Pure GA."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    combos = [
        ("OX", "Swap"),
        ("OX", "Inversion"),
        ("PMX", "Swap"),
        ("PMX", "Inversion"),
    ]
    rows: list[dict] = []
    histories: dict[str, dict[str, list[list[float]]]] = {}

    for inst in instances:
        histories[inst.name] = {}
        for cx, mut in combos:
            label = f"{cx}+{mut}"
            histories[inst.name][label] = []
            for seed in seeds:
                cfg = GAConfig(
                    pop_size=pop_size,
                    generations=generations,
                    crossover=cx,
                    mutation=mut,
                    memetic=False,
                    seed=seed,
                )
                res = solve_genetic(inst, cfg)
                rows.append(
                    _make_row(
                        inst,
                        "Pure_GA",
                        cx,
                        mut,
                        seed,
                        res.distance,
                        res.num_vehicles,
                        res.runtime_sec,
                    )
                )
                if res.history is not None:
                    histories[inst.name][label].append(res.history)

    save_csv(rows, out / "phase1_ablation.csv")
    save_csv(aggregate_results(rows), out / "phase1_summary.csv")
    (out / "phase1_histories.json").write_text(
        json.dumps(histories), encoding="utf-8"
    )
    return rows


def select_best_operators(ablation_rows: list[dict]) -> tuple[str, str]:
    """Select the (crossover, mutation) pair with the lowest overall mean distance."""
    summary = aggregate_results(ablation_rows)
    by_pair: dict[tuple[str, str], list[float]] = {}
    for row in summary:
        pair = (str(row["crossover"]), str(row["mutation"]))
        by_pair.setdefault(pair, []).append(float(row["mean_distance"]))
    best_pair = min(by_pair.keys(), key=lambda p: float(np.mean(by_pair[p])))
    return best_pair


def run_phase2_comparison(
    instances: list[CVRPInstance],
    seeds: list[int],
    *,
    crossover: str = "OX",
    mutation: str = "Inversion",
    pop_size: int = 60,
    generations: int = 150,
    local_search_rate: float = 0.30,
    output_dir: str | Path = "results",
) -> tuple[list[dict], dict]:
    """Phase 2: Compare Greedy Baseline vs. Pure GA vs. Memetic GA across seeds."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    histories: dict[str, dict[str, list[list[float]]]] = {}
    best_solutions: dict[str, dict[str, dict]] = {}

    for inst in instances:
        histories[inst.name] = {"Pure_GA": [], "Memetic_GA": []}
        best_solutions[inst.name] = {}

        # Deterministic Greedy baseline
        greedy_res = solve_greedy(inst)
        rows.append(
            _make_row(
                inst,
                "Greedy",
                "-",
                "-",
                0,
                greedy_res.distance,
                greedy_res.num_vehicles,
                greedy_res.runtime_sec,
            )
        )
        best_solutions[inst.name]["Greedy"] = {
            "distance": greedy_res.distance,
            "num_vehicles": greedy_res.num_vehicles,
            "routes": greedy_res.routes,
        }

        for method_name, is_memetic in [("Pure_GA", False), ("Memetic_GA", True)]:
            best_dist = float("inf")
            best_res = None
            for seed in seeds:
                cfg = GAConfig(
                    pop_size=pop_size,
                    generations=generations,
                    crossover=crossover,
                    mutation=mutation,
                    memetic=is_memetic,
                    local_search_rate=local_search_rate,
                    seed=seed,
                )
                res = solve_genetic(inst, cfg)
                rows.append(
                    _make_row(
                        inst,
                        method_name,
                        crossover,
                        mutation,
                        seed,
                        res.distance,
                        res.num_vehicles,
                        res.runtime_sec,
                    )
                )
                if res.history is not None:
                    histories[inst.name][method_name].append(res.history)
                if res.distance < best_dist:
                    best_dist = res.distance
                    best_res = res

            if best_res is not None:
                best_solutions[inst.name][method_name] = {
                    "distance": best_res.distance,
                    "num_vehicles": best_res.num_vehicles,
                    "routes": best_res.routes,
                }

    save_csv(rows, out / "phase2_results.csv")
    save_csv(aggregate_results(rows), out / "phase2_summary.csv")
    save_csv(compare_pure_vs_memetic(rows), out / "phase2_stats_tests.csv")
    (out / "phase2_histories.json").write_text(
        json.dumps(histories), encoding="utf-8"
    )
    (out / "best_solutions.json").write_text(
        json.dumps(best_solutions, indent=2), encoding="utf-8"
    )
    return rows, histories


def main() -> None:
    parser = argparse.ArgumentParser(description="Run CVRP Memetic GA experiments.")
    parser.add_argument("--phase1-seeds", type=int, default=10)
    parser.add_argument("--phase2-seeds", type=int, default=30)
    parser.add_argument("--pop-size", type=int, default=60)
    parser.add_argument("--generations", type=int, default=150)
    parser.add_argument("--ls-rate", type=float, default=0.30)
    parser.add_argument("--output-dir", type=str, default="results")
    args = parser.parse_args()

    cvrplib_instances = load_cvrplib_suite("data/cvrplib")
    recife_instances = load_recife_suite("data/recife_ubs")

    # Phase 1 on 2 representative CVRPLIB instances (A-n32-k5, A-n60-k9)
    p1_instances = [cvrplib_instances[0], cvrplib_instances[2]]
    p1_seeds = list(range(1, args.phase1_seeds + 1))
    p1_rows = run_phase1_ablation(
        p1_instances,
        p1_seeds,
        pop_size=args.pop_size,
        generations=args.generations,
        output_dir=args.output_dir,
    )
    best_cx, best_mut = select_best_operators(p1_rows)
    print(f"Phase 1 selected operators: crossover={best_cx}, mutation={best_mut}")

    # Phase 2 on all 4 CVRPLIB + Recife road-network instance
    p2_instances = cvrplib_instances + recife_instances
    p2_seeds = list(range(1, args.phase2_seeds + 1))
    p2_rows, p2_histories = run_phase2_comparison(
        p2_instances,
        p2_seeds,
        crossover=best_cx,
        mutation=best_mut,
        pop_size=args.pop_size,
        generations=args.generations,
        local_search_rate=args.ls_rate,
        output_dir=args.output_dir,
    )

    out_dir = Path(args.output_dir)
    plot_convergence_curves(p2_histories, out_dir)
    plot_comparative_boxplots(p2_rows, out_dir)

    best_sols = json.loads((out_dir / "best_solutions.json").read_text(encoding="utf-8"))
    recife_road = recife_instances[0]
    recife_routes = best_sols[recife_road.name]["Memetic_GA"]["routes"]
    generate_recife_map(recife_road, recife_routes, out_dir / "recife_map.html")
    print(f"Phase 2, plots, and Recife map complete. Results saved in {out_dir}/")


if __name__ == "__main__":
    main()
