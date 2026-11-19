"""Automated multi-seed experiment runner for CVRP ablation and benchmarking."""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
from rich.console import Console

from src.data.cvrplib_loader import load_cvrplib
from src.data.models import CVRPInstance
from src.data.recife_loader import load_recife
from src.experiments.hpo import (
    METHOD_MEMETIC,
    METHOD_PURE,
    load_tuned_configs,
    run_hpo_suite,
)
from src.experiments.map_recife import generate_recife_map
from src.experiments.plots import plot_comparative_boxplots, plot_convergence_curves
from src.experiments.progress import (
    create_experiment_progress,
    format_run_detail,
    render_phase1_summary,
    render_phase2_summary,
)
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
    show_progress: bool = True,
    console: Console | None = None,
) -> list[dict]:
    """Phase 1: Ablation over (OX, PMX) x (Swap, Inversion) on Pure GA."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    active_console = console or Console()

    combos = [
        ("OX", "Swap"),
        ("OX", "Inversion"),
        ("PMX", "Swap"),
        ("PMX", "Inversion"),
    ]
    rows: list[dict] = []
    histories: dict[str, dict[str, list[list[float]]]] = {}
    total_runs = len(instances) * len(combos) * len(seeds)

    with create_experiment_progress(
        console=active_console, disable=not show_progress
    ) as progress:
        task_id = progress.add_task(
            "Phase 1: Ablation", total=total_runs, detail="starting..."
        )
        for inst in instances:
            histories[inst.name] = {}
            for cx, mut in combos:
                label = f"{cx}+{mut}"
                histories[inst.name][label] = []
                best_dist: float | None = None
                for seed_idx, seed in enumerate(seeds, start=1):
                    progress.update(
                        task_id,
                        detail=format_run_detail(
                            inst.name,
                            label,
                            seed_idx,
                            len(seeds),
                            best_distance=best_dist,
                            optimal_value=inst.optimal_value,
                        ),
                    )
                    cfg = GAConfig(
                        pop_size=pop_size,
                        generations=generations,
                        crossover=cx,
                        mutation=mut,
                        memetic=False,
                        seed=seed,
                    )
                    res = solve_genetic(inst, cfg)
                    best_dist = (
                        res.distance
                        if best_dist is None
                        else min(best_dist, res.distance)
                    )
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
                    progress.update(
                        task_id,
                        advance=1,
                        detail=format_run_detail(
                            inst.name,
                            label,
                            seed_idx,
                            len(seeds),
                            last_distance=res.distance,
                            best_distance=best_dist,
                            optimal_value=inst.optimal_value,
                        ),
                    )

    save_csv(rows, out / "phase1_ablation.csv")
    save_csv(aggregate_results(rows), out / "phase1_summary.csv")
    (out / "phase1_histories.json").write_text(json.dumps(histories), encoding="utf-8")
    if show_progress and rows:
        render_phase1_summary(active_console, rows, select_best_operators(rows))
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
    pure_ga_config: GAConfig | None = None,
    memetic_ga_config: GAConfig | None = None,
    output_dir: str | Path = "results",
    show_progress: bool = True,
    console: Console | None = None,
) -> tuple[list[dict], dict]:
    """Phase 2: Compare Greedy Baseline vs. Pure GA vs. Memetic GA across seeds."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    active_console = console or Console()

    rows: list[dict] = []
    histories: dict[str, dict[str, list[list[float]]]] = {}
    best_solutions: dict[str, dict[str, dict]] = {}
    total_runs = len(instances) * (1 + 2 * len(seeds))

    with create_experiment_progress(
        console=active_console, disable=not show_progress
    ) as progress:
        task_id = progress.add_task(
            "Phase 2: Comparison", total=total_runs, detail="starting..."
        )
        for inst in instances:
            histories[inst.name] = {"Pure_GA": [], "Memetic_GA": []}
            best_solutions[inst.name] = {}

            # Deterministic Greedy baseline
            progress.update(
                task_id,
                detail=format_run_detail(
                    inst.name,
                    "Greedy",
                    1,
                    1,
                    optimal_value=inst.optimal_value,
                ),
            )
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
            progress.update(
                task_id,
                advance=1,
                detail=format_run_detail(
                    inst.name,
                    "Greedy",
                    1,
                    1,
                    last_distance=greedy_res.distance,
                    best_distance=greedy_res.distance,
                    optimal_value=inst.optimal_value,
                ),
            )

            method_configs = [
                ("Pure_GA", False, pure_ga_config),
                ("Memetic_GA", True, memetic_ga_config),
            ]
            for method_name, is_memetic, override_cfg in method_configs:
                base_cfg = (
                    replace(override_cfg, generations=generations, memetic=is_memetic)
                    if override_cfg is not None
                    else GAConfig(
                        pop_size=pop_size,
                        generations=generations,
                        crossover=crossover,
                        mutation=mutation,
                        memetic=is_memetic,
                        local_search_rate=local_search_rate,
                    )
                )
                best_dist = float("inf")
                best_res = None
                method_label = (
                    f"{method_name} ({base_cfg.crossover}+{base_cfg.mutation})"
                )
                for seed_idx, seed in enumerate(seeds, start=1):
                    current_best = best_dist if best_dist < float("inf") else None
                    progress.update(
                        task_id,
                        detail=format_run_detail(
                            inst.name,
                            method_label,
                            seed_idx,
                            len(seeds),
                            best_distance=current_best,
                            optimal_value=inst.optimal_value,
                        ),
                    )
                    cfg = replace(base_cfg, seed=seed)
                    res = solve_genetic(inst, cfg)
                    rows.append(
                        _make_row(
                            inst,
                            method_name,
                            cfg.crossover,
                            cfg.mutation,
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
                    progress.update(
                        task_id,
                        advance=1,
                        detail=format_run_detail(
                            inst.name,
                            method_label,
                            seed_idx,
                            len(seeds),
                            last_distance=res.distance,
                            best_distance=best_dist,
                            optimal_value=inst.optimal_value,
                        ),
                    )

                if best_res is not None:
                    best_solutions[inst.name][method_name] = {
                        "distance": best_res.distance,
                        "num_vehicles": best_res.num_vehicles,
                        "routes": best_res.routes,
                    }

    save_csv(rows, out / "phase2_results.csv")
    save_csv(aggregate_results(rows), out / "phase2_summary.csv")
    save_csv(compare_pure_vs_memetic(rows), out / "phase2_stats_tests.csv")
    (out / "phase2_histories.json").write_text(json.dumps(histories), encoding="utf-8")
    (out / "best_solutions.json").write_text(
        json.dumps(best_solutions, indent=2), encoding="utf-8"
    )
    if show_progress and rows:
        render_phase2_summary(active_console, rows)
    return rows, histories


def build_arg_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser for the experiment runner."""
    parser = argparse.ArgumentParser(description="Run CVRP Memetic GA experiments.")
    parser.add_argument("--phase1-seeds", type=int, default=10)
    parser.add_argument("--phase2-seeds", type=int, default=30)
    parser.add_argument("--pop-size", type=int, default=60)
    parser.add_argument("--generations", type=int, default=150)
    parser.add_argument("--ls-rate", type=float, default=0.30)
    parser.add_argument("--output-dir", type=str, default="results")
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable live rich progress bars and phase summary tables.",
    )
    tune_group = parser.add_mutually_exclusive_group()
    tune_group.add_argument(
        "--tuned-config",
        type=str,
        default=None,
        help="Path to hpo_best_configs.json; skips Phase 1 and uses tuned configs in Phase 2.",
    )
    tune_group.add_argument(
        "--tune",
        action="store_true",
        help="Run Optuna HPO before Phase 2 instead of Phase 1 ablation.",
    )
    parser.add_argument(
        "--hpo-trials",
        type=int,
        default=25,
        help="Number of Optuna trials per method when --tune is set.",
    )
    parser.add_argument(
        "--hpo-seeds",
        type=int,
        default=3,
        help="Number of evaluation seeds per HPO trial when --tune is set.",
    )
    parser.add_argument(
        "--hpo-generations",
        type=int,
        default=None,
        help="Generation budget per HPO evaluation (defaults to --generations).",
    )
    parser.add_argument(
        "--hpo-seed",
        type=int,
        default=42,
        help="Master seed for Optuna TPESampler when --tune is set.",
    )
    return parser


def run_post_processing(
    p2_rows: list[dict],
    p2_histories: dict,
    recife_road: CVRPInstance,
    out_dir: Path,
    *,
    show_progress: bool = True,
    console: Console | None = None,
) -> None:
    """Generate convergence plots, comparative boxplots, and Recife HTML map."""
    active_console = console or Console()
    best_sols = json.loads(
        (out_dir / "best_solutions.json").read_text(encoding="utf-8")
    )
    recife_routes = best_sols[recife_road.name]["Memetic_GA"]["routes"]

    steps = [
        (
            "Plotting convergence curves",
            lambda: plot_convergence_curves(p2_histories, out_dir),
        ),
        (
            "Plotting comparative boxplots",
            lambda: plot_comparative_boxplots(p2_rows, out_dir),
        ),
        (
            "Generating Recife HTML map",
            lambda: generate_recife_map(
                recife_road, recife_routes, out_dir / "recife_map.html"
            ),
        ),
    ]

    with create_experiment_progress(
        console=active_console, disable=not show_progress
    ) as progress:
        task_id = progress.add_task(
            "Post-processing", total=len(steps), detail="starting..."
        )
        for label, action in steps:
            progress.update(task_id, detail=label)
            action()
            progress.update(task_id, advance=1, detail=f"{label} (done)")


def main(argv: list[str] | None = None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    show_progress = not args.no_progress
    console = Console()

    pure_tuned_cfg: GAConfig | None = None
    memetic_tuned_cfg: GAConfig | None = None

    if args.tuned_config is not None:
        try:
            tuned = load_tuned_configs(args.tuned_config, require_both=True)
        except (FileNotFoundError, ValueError, TypeError) as exc:
            parser.error(str(exc))
        pure_tuned_cfg = tuned[METHOD_PURE]
        memetic_tuned_cfg = tuned[METHOD_MEMETIC]
        console.print(
            f"Loaded tuned configs from {args.tuned_config} "
            f"(Pure_GA: {pure_tuned_cfg.crossover}+{pure_tuned_cfg.mutation}, "
            f"Memetic_GA: {memetic_tuned_cfg.crossover}+{memetic_tuned_cfg.mutation}); "
            "skipping Phase 1 ablation."
        )

    cvrplib_instances = load_cvrplib_suite("data/cvrplib")
    recife_instances = load_recife_suite("data/recife_ubs")

    # Tuning / Phase 1 representative subset (A-n32-k5, A-n60-k9)
    p1_instances = [cvrplib_instances[0], cvrplib_instances[2]]

    if args.tune:
        hpo_gens = (
            args.hpo_generations
            if args.hpo_generations is not None
            else args.generations
        )
        hpo_seeds = list(range(1, args.hpo_seeds + 1))
        run_hpo_suite(
            p1_instances,
            hpo_seeds,
            n_trials=args.hpo_trials,
            generations=hpo_gens,
            hpo_seed=args.hpo_seed,
            output_dir=args.output_dir,
            show_progress=show_progress,
            console=console,
        )
        tuned = load_tuned_configs(
            Path(args.output_dir) / "hpo_best_configs.json", require_both=True
        )
        pure_tuned_cfg = tuned[METHOD_PURE]
        memetic_tuned_cfg = tuned[METHOD_MEMETIC]
        best_cx, best_mut = pure_tuned_cfg.crossover, pure_tuned_cfg.mutation
    elif pure_tuned_cfg is not None and memetic_tuned_cfg is not None:
        best_cx, best_mut = pure_tuned_cfg.crossover, pure_tuned_cfg.mutation
    else:
        p1_seeds = list(range(1, args.phase1_seeds + 1))
        p1_rows = run_phase1_ablation(
            p1_instances,
            p1_seeds,
            pop_size=args.pop_size,
            generations=args.generations,
            output_dir=args.output_dir,
            show_progress=show_progress,
            console=console,
        )
        best_cx, best_mut = select_best_operators(p1_rows)
        console.print(
            f"Phase 1 selected operators: crossover={best_cx}, mutation={best_mut}"
        )

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
        pure_ga_config=pure_tuned_cfg,
        memetic_ga_config=memetic_tuned_cfg,
        output_dir=args.output_dir,
        show_progress=show_progress,
        console=console,
    )

    out_dir = Path(args.output_dir)
    run_post_processing(
        p2_rows,
        p2_histories,
        recife_instances[0],
        out_dir,
        show_progress=show_progress,
        console=console,
    )
    console.print(
        f"[bold green]Experiment campaign complete.[/bold green] "
        f"Phase 2, plots, and Recife map saved in {out_dir}/"
    )


if __name__ == "__main__":
    main()
