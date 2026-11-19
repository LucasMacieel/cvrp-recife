"""Rich progress bars, live telemetry formatting, and summary tables for experiments."""

from __future__ import annotations

from collections import defaultdict

import numpy as np
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table

from src.experiments.stats import aggregate_results, compute_gap_pct


def create_experiment_progress(
    console: Console | None = None,
    *,
    disable: bool = False,
) -> Progress:
    """Create a Rich Progress instance configured with run-level telemetry columns."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        TextColumn("{task.fields[detail]}"),
        console=console,
        disable=disable,
    )


def format_run_detail(
    instance_name: str,
    config_label: str,
    seed_idx: int,
    total_seeds: int,
    *,
    last_distance: float | None = None,
    best_distance: float | None = None,
    optimal_value: float | None = None,
) -> str:
    """Format live per-run telemetry string for the progress bar detail column."""
    parts = [
        f"inst={instance_name}",
        config_label,
        f"seed {seed_idx}/{total_seeds}",
    ]
    if last_distance is not None:
        parts.append(f"last={last_distance:.2f}")
    if best_distance is not None:
        gap = compute_gap_pct(best_distance, optimal_value)
        if gap is not None:
            parts.append(f"best={best_distance:.2f} (gap={gap:.2f}%)")
        else:
            parts.append(f"best={best_distance:.2f}")
    return " | ".join(parts)


def build_phase1_summary_table(
    ablation_rows: list[dict],
    selected_pair: tuple[str, str],
) -> Table:
    """Build a Rich summary table ranking Phase 1 operator pairs."""
    summary = aggregate_results(ablation_rows)
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in summary:
        grouped[(str(row["crossover"]), str(row["mutation"]))].append(row)

    aggregated_pairs: list[tuple[tuple[str, str], int, float, float, float | None, float]] = []
    for pair, items in grouped.items():
        total_runs = sum(int(item["n_runs"]) for item in items)
        mean_dist = float(np.mean([float(item["mean_distance"]) for item in items]))
        best_dist = float(np.min([float(item["best_distance"]) for item in items]))
        gaps = [float(item["mean_gap_pct"]) for item in items if item["mean_gap_pct"] is not None]
        mean_gap = float(np.mean(gaps)) if gaps else None
        mean_time = float(np.mean([float(item["mean_runtime_sec"]) for item in items]))
        aggregated_pairs.append((pair, total_runs, mean_dist, best_dist, mean_gap, mean_time))

    aggregated_pairs.sort(key=lambda item: item[2])

    table = Table(title="Phase 1: Operator Ablation Summary")
    table.add_column("Operators", style="cyan", no_wrap=True)
    table.add_column("Runs", justify="right")
    table.add_column("Mean Dist", justify="right")
    table.add_column("Best Dist", justify="right")
    table.add_column("Mean Gap %", justify="right")
    table.add_column("Mean Time (s)", justify="right")
    table.add_column("Selected", justify="center")

    for pair, total_runs, mean_dist, best_dist, mean_gap, mean_time in aggregated_pairs:
        is_selected = pair == selected_pair
        gap_str = f"{mean_gap:.2f}%" if mean_gap is not None else "-"
        selected_str = "[bold green]Selected[/bold green]" if is_selected else "-"
        table.add_row(
            f"{pair[0]}+{pair[1]}",
            str(total_runs),
            f"{mean_dist:.2f}",
            f"{best_dist:.2f}",
            gap_str,
            f"{mean_time:.3f}",
            selected_str,
        )
    return table


def build_phase2_summary_table(phase2_rows: list[dict]) -> Table:
    """Build a Rich summary table of Phase 2 per-instance and method metrics."""
    summary = aggregate_results(phase2_rows)

    table = Table(title="Phase 2: Benchmark Comparison Summary")
    table.add_column("Instance", style="cyan", no_wrap=True)
    table.add_column("Method", style="magenta", no_wrap=True)
    table.add_column("Runs", justify="right")
    table.add_column("Mean Dist", justify="right")
    table.add_column("Best Dist", justify="right")
    table.add_column("Best Gap %", justify="right")
    table.add_column("Mean Time (s)", justify="right")

    for row in summary:
        gap_val = row["best_gap_pct"]
        gap_str = f"{float(gap_val):.2f}%" if gap_val is not None else "-"
        table.add_row(
            str(row["instance"]),
            str(row["method"]),
            str(row["n_runs"]),
            f"{float(row['mean_distance']):.2f}",
            f"{float(row['best_distance']):.2f}",
            gap_str,
            f"{float(row['mean_runtime_sec']):.3f}",
        )
    return table


def render_phase1_summary(
    console: Console,
    ablation_rows: list[dict],
    selected_pair: tuple[str, str],
) -> None:
    """Print the Phase 1 summary table to the provided console."""
    console.print(build_phase1_summary_table(ablation_rows, selected_pair))


def render_phase2_summary(console: Console, phase2_rows: list[dict]) -> None:
    """Print the Phase 2 summary table to the provided console."""
    console.print(build_phase2_summary_table(phase2_rows))


def format_hpo_detail(
    method_name: str,
    trial_num: int,
    total_trials: int,
    *,
    last_objective: float | None = None,
    best_objective: float | None = None,
) -> str:
    """Format live per-trial telemetry string for HPO progress bar."""
    parts = [method_name, f"trial {trial_num}/{total_trials}"]
    if last_objective is not None:
        parts.append(f"last={last_objective:.2f}%")
    if best_objective is not None:
        parts.append(f"best={best_objective:.2f}%")
    return " | ".join(parts)


def build_hpo_summary_table(results: dict) -> Table:
    """Build a Rich summary table for HPO best configurations."""
    table = Table(title="Hyperparameter Optimization Summary")
    table.add_column("Method", style="cyan", no_wrap=True)
    table.add_column("Best Trial", justify="right")
    table.add_column("Best Obj (%)", justify="right")
    table.add_column("Operators", style="magenta", no_wrap=True)
    table.add_column("Pop", justify="right")
    table.add_column("CX Rate", justify="right")
    table.add_column("Mut Rate", justify="right")
    table.add_column("k / Elite", justify="center")
    table.add_column("LS Rate / Passes", justify="center")

    for method in ("Pure_GA", "Memetic_GA"):
        entry = results.get(method)
        if not entry:
            continue
        cfg = entry["config"]
        ls_str = (
            f"{cfg['local_search_rate']:.2f} / {cfg['local_search_max_passes']}"
            if cfg.get("memetic")
            else "-"
        )
        table.add_row(
            method,
            str(entry["best_trial_number"]),
            f"{float(entry['best_objective']):.2f}%",
            f"{cfg['crossover']}+{cfg['mutation']}",
            str(cfg["pop_size"]),
            f"{float(cfg['crossover_rate']):.2f}",
            f"{float(cfg['mutation_rate']):.2f}",
            f"{cfg['tournament_k']} / {cfg['elite_size']}",
            ls_str,
        )
    return table


def render_hpo_summary(console: Console, results: dict) -> None:
    """Print the HPO summary table to the provided console."""
    console.print(build_hpo_summary_table(results))
