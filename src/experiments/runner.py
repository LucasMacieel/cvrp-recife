"""Automated multi-seed experiment runner for CVRP Phase 1 (Bayesian HPO) and Phase 2 benchmarking."""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

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
from src.experiments.stats import (
    aggregate_results,
    compare_pure_vs_memetic,
    compute_gap_pct,
    save_csv,
)
from src.solver.genetic import GAConfig, solve_genetic
from src.solver.greedy import solve_greedy


def load_cvrplib_suite(data_dir: str | Path = "data/cvrplib") -> list[CVRPInstance]:
    """Load the 3 benchmark CVRPLIB instances in increasing size order."""
    base = Path(data_dir)
    names = ["A-n32-k5.vrp", "A-n45-k6.vrp", "A-n60-k9.vrp"]
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
    """Create the CLI argument parser for the Phase 1 (HPO) -> Phase 2 runner."""
    parser = argparse.ArgumentParser(
        description="Run CVRP Phase 1 (Bayesian HPO) and Phase 2 benchmarking."
    )
    parser.add_argument(
        "--phase2-seeds",
        type=int,
        default=30,
        help="Number of random seeds per instance/method in Phase 2.",
    )
    parser.add_argument(
        "--generations",
        type=int,
        default=150,
        help="Generation budget per Phase 2 run.",
    )
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
        help="Path to hpo_best_configs.json; skips inline Phase 1 HPO and uses pre-computed configs in Phase 2.",
    )
    tune_group.add_argument(
        "--tune",
        action="store_true",
        help="Optional alias for default inline Phase 1 Bayesian HPO before Phase 2.",
    )
    parser.add_argument(
        "--hpo-trials",
        type=int,
        default=30,
        help="Number of Optuna trials per method for inline Phase 1 HPO.",
    )
    parser.add_argument(
        "--hpo-seeds",
        type=int,
        default=3,
        help="Number of evaluation seeds per inline Phase 1 HPO trial.",
    )
    parser.add_argument(
        "--hpo-generations",
        type=int,
        default=100,
        help="Generation budget per inline Phase 1 HPO evaluation.",
    )
    parser.add_argument(
        "--hpo-seed",
        type=int,
        default=42,
        help="Master seed for Optuna TPESampler in inline Phase 1 HPO.",
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
    """Generate convergence plots, comparative boxplots, best-solution route plot, and Recife HTML map."""
    active_console = console or Console()
    best_sols = json.loads(
        (out_dir / "best_solutions.json").read_text(encoding="utf-8")
    )
    recife_best = best_sols[recife_road.name]["Memetic_GA"]
    recife_routes = recife_best["routes"]
    recife_dist = float(recife_best["distance"])

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
            "Plotting best Recife routes",
            lambda: plot_best_solution_routes(
                recife_road,
                recife_routes,
                recife_dist,
                out_dir / f"best_solution_{recife_road.name}.png",
            ),
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
            "skipping inline Phase 1 HPO."
        )

    cvrplib_instances = load_cvrplib_suite("data/cvrplib")
    recife_instances = load_recife_suite("data/recife_ubs")

    if args.tuned_config is None:
        hpo_seeds = list(range(1, args.hpo_seeds + 1))
        run_hpo_suite(
            cvrplib_instances,
            hpo_seeds,
            n_trials=args.hpo_trials,
            generations=args.hpo_generations,
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

    # Phase 2 on all 3 CVRPLIB instances + held-out Recife road-network instance
    p2_instances = cvrplib_instances + recife_instances
    p2_seeds = list(range(1, args.phase2_seeds + 1))
    p2_rows, p2_histories = run_phase2_comparison(
        p2_instances,
        p2_seeds,
        generations=args.generations,
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
