"""Bayesian hyperparameter optimization (Optuna TPE) for Pure GA and Memetic GA."""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import replace
from pathlib import Path

import numpy as np
import optuna
from rich.console import Console

from src.data.cvrplib_loader import load_cvrplib
from src.data.models import CVRPInstance
from src.data.recife_loader import load_recife
from src.experiments.progress import (
    create_experiment_progress,
    format_hpo_detail,
    render_hpo_summary,
)
from src.experiments.stats import compute_gap_pct, save_csv
from src.solver.genetic import GAConfig, solve_genetic
from src.solver.greedy import solve_greedy
from src.solver.operators import CROSSOVER_OPERATORS, MUTATION_OPERATORS

METHOD_PURE = "Pure_GA"
METHOD_MEMETIC = "Memetic_GA"
VALID_METHODS = (METHOD_PURE, METHOD_MEMETIC)
DEFAULT_CVRPLIB_NAMES = (
    "A-n32-k5.vrp",
    "A-n45-k6.vrp",
    "A-n60-k9.vrp",
)


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def sample_ga_config(
    trial: optuna.Trial,
    *,
    memetic: bool,
    generations: int,
) -> GAConfig:
    """Sample a candidate GAConfig from the Optuna search space."""
    crossover = trial.suggest_categorical(
        "crossover", sorted(CROSSOVER_OPERATORS.keys())
    )
    mutation = trial.suggest_categorical("mutation", sorted(MUTATION_OPERATORS.keys()))
    pop_size = trial.suggest_int("pop_size", 30, 120, step=10)
    crossover_rate = trial.suggest_float("crossover_rate", 0.60, 0.98)
    mutation_rate = trial.suggest_float("mutation_rate", 0.05, 0.50)
    tournament_k = trial.suggest_int("tournament_k", 2, 6)
    elite_size = trial.suggest_int("elite_size", 1, 6)

    if memetic:
        local_search_rate = trial.suggest_float("local_search_rate", 0.10, 0.60)
        local_search_max_passes = trial.suggest_int(
            "local_search_max_passes", 5, 25, step=5
        )
    else:
        local_search_rate = 0.0
        local_search_max_passes = 15

    return GAConfig(
        pop_size=pop_size,
        generations=generations,
        crossover_rate=crossover_rate,
        mutation_rate=mutation_rate,
        tournament_k=tournament_k,
        elite_size=elite_size,
        crossover=crossover,
        mutation=mutation,
        memetic=memetic,
        local_search_rate=local_search_rate,
        local_search_max_passes=local_search_max_passes,
    )


def config_to_dict(config: GAConfig) -> dict:
    """Serialize a GAConfig to the HPO JSON config dictionary (without generations/seed)."""
    data: dict = {
        "pop_size": int(config.pop_size),
        "crossover_rate": round(float(config.crossover_rate), 6),
        "mutation_rate": round(float(config.mutation_rate), 6),
        "tournament_k": int(config.tournament_k),
        "elite_size": int(config.elite_size),
        "crossover": str(config.crossover),
        "mutation": str(config.mutation),
        "memetic": bool(config.memetic),
    }
    if config.memetic:
        data["local_search_rate"] = round(float(config.local_search_rate), 6)
        data["local_search_max_passes"] = int(config.local_search_max_passes)
    return data


def _validate_and_build_config(method: str, raw_cfg: object) -> GAConfig:
    """Validate a raw config dictionary for a method and return a GAConfig."""
    if not isinstance(raw_cfg, dict):
        raise TypeError(f"{method}.config must be a JSON object.")

    expected_memetic = method == METHOD_MEMETIC
    required_keys = {
        "pop_size",
        "crossover_rate",
        "mutation_rate",
        "tournament_k",
        "elite_size",
        "crossover",
        "mutation",
        "memetic",
    }
    if expected_memetic:
        required_keys.update({"local_search_rate", "local_search_max_passes"})

    missing = sorted(required_keys - set(raw_cfg.keys()))
    if missing:
        raise ValueError(f"{method}.config missing required keys: {missing}")

    crossover = raw_cfg["crossover"]
    if crossover not in CROSSOVER_OPERATORS:
        raise ValueError(
            f"{method}.config.crossover {crossover!r} must be one of {sorted(CROSSOVER_OPERATORS)}"
        )

    mutation = raw_cfg["mutation"]
    if mutation not in MUTATION_OPERATORS:
        raise ValueError(
            f"{method}.config.mutation {mutation!r} must be one of {sorted(MUTATION_OPERATORS)}"
        )

    pop_size = raw_cfg["pop_size"]
    if not _is_int(pop_size) or pop_size < 2:
        raise ValueError(
            f"{method}.config.pop_size must be an integer >= 2, got {pop_size!r}"
        )

    elite_size = raw_cfg["elite_size"]
    if not _is_int(elite_size) or not (1 <= elite_size < pop_size):
        raise ValueError(
            f"{method}.config.elite_size must satisfy 1 <= elite_size < pop_size ({pop_size}), got {elite_size!r}"
        )

    tournament_k = raw_cfg["tournament_k"]
    if not _is_int(tournament_k) or not (2 <= tournament_k <= pop_size):
        raise ValueError(
            f"{method}.config.tournament_k must satisfy 2 <= tournament_k <= pop_size ({pop_size}), got {tournament_k!r}"
        )

    crossover_rate = raw_cfg["crossover_rate"]
    if not _is_number(crossover_rate) or not (0.0 <= float(crossover_rate) <= 1.0):
        raise ValueError(
            f"{method}.config.crossover_rate must be in [0.0, 1.0], got {crossover_rate!r}"
        )

    mutation_rate = raw_cfg["mutation_rate"]
    if not _is_number(mutation_rate) or not (0.0 <= float(mutation_rate) <= 1.0):
        raise ValueError(
            f"{method}.config.mutation_rate must be in [0.0, 1.0], got {mutation_rate!r}"
        )

    memetic = raw_cfg["memetic"]
    if not isinstance(memetic, bool) or memetic != expected_memetic:
        raise ValueError(
            f"{method}.config.memetic must be {expected_memetic!r}, got {memetic!r}"
        )

    if expected_memetic:
        ls_rate = raw_cfg["local_search_rate"]
        if not _is_number(ls_rate) or not (0.0 <= float(ls_rate) <= 1.0):
            raise ValueError(
                f"{method}.config.local_search_rate must be in [0.0, 1.0], got {ls_rate!r}"
            )
        ls_passes = raw_cfg["local_search_max_passes"]
        if not _is_int(ls_passes) or ls_passes < 1:
            raise ValueError(
                f"{method}.config.local_search_max_passes must be an integer >= 1, got {ls_passes!r}"
            )
        ls_rate_val = float(ls_rate)
        ls_passes_val = int(ls_passes)
    else:
        ls_rate_val = 0.0
        ls_passes_val = 15

    return GAConfig(
        pop_size=int(pop_size),
        crossover_rate=float(crossover_rate),
        mutation_rate=float(mutation_rate),
        tournament_k=int(tournament_k),
        elite_size=int(elite_size),
        crossover=str(crossover),
        mutation=str(mutation),
        memetic=memetic,
        local_search_rate=ls_rate_val,
        local_search_max_passes=ls_passes_val,
    )


def compute_greedy_baselines(instances: list[CVRPInstance]) -> dict[str, float]:
    """Precompute deterministic Greedy distances for instances lacking known optima."""
    baselines: dict[str, float] = {}
    for inst in instances:
        if inst.optimal_value is None or inst.optimal_value <= 0:
            baselines[inst.name] = float(solve_greedy(inst).distance)
    return baselines


def evaluate_ga_config(
    config: GAConfig,
    instances: list[CVRPInstance],
    seeds: list[int],
    greedy_baselines: dict[str, float] | None = None,
) -> float:
    """Evaluate a GAConfig across all (instance, seed) pairs using normalized % gap."""
    if not instances or not seeds:
        raise ValueError("instances and seeds must be non-empty.")

    baselines = (
        greedy_baselines
        if greedy_baselines is not None
        else compute_greedy_baselines(instances)
    )
    scores: list[float] = []

    for inst in instances:
        for seed in seeds:
            run_cfg = replace(config, seed=seed)
            res = solve_genetic(inst, run_cfg)
            gap = compute_gap_pct(res.distance, inst.optimal_value)
            if gap is not None:
                scores.append(gap)
            else:
                ref = baselines[inst.name]
                score = ((float(res.distance) - ref) / ref) * 100.0 if ref > 0 else 0.0
                scores.append(score)

    return float(np.mean(scores))


def optimize_ga(
    method: str,
    instances: list[CVRPInstance],
    seeds: list[int],
    *,
    n_trials: int = 30,
    generations: int = 100,
    hpo_seed: int = 42,
    greedy_baselines: dict[str, float] | None = None,
    show_progress: bool = True,
    console: Console | None = None,
) -> tuple[dict, list[dict]]:
    """Run an Optuna TPE study for a single GA method (Pure_GA or Memetic_GA)."""
    if method not in VALID_METHODS:
        raise ValueError(f"Unknown method {method!r}; choose from {VALID_METHODS}")
    if n_trials < 1:
        raise ValueError(f"n_trials must be >= 1, got {n_trials}")

    memetic = method == METHOD_MEMETIC
    baselines = (
        greedy_baselines
        if greedy_baselines is not None
        else compute_greedy_baselines(instances)
    )
    active_console = console or Console()

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    sampler = optuna.samplers.TPESampler(seed=hpo_seed)
    study = optuna.create_study(direction="minimize", sampler=sampler)

    trial_rows: list[dict] = []
    best_obj: float | None = None

    with create_experiment_progress(
        console=active_console, disable=not show_progress
    ) as progress:
        task_id = progress.add_task(
            f"HPO: {method}", total=n_trials, detail="starting..."
        )

        def _objective(trial: optuna.Trial) -> float:
            nonlocal best_obj
            trial_idx = trial.number + 1
            progress.update(
                task_id,
                detail=format_hpo_detail(
                    method, trial_idx, n_trials, best_objective=best_obj
                ),
            )
            t0 = time.perf_counter()
            cfg = sample_ga_config(trial, memetic=memetic, generations=generations)
            obj = evaluate_ga_config(cfg, instances, seeds, baselines)
            duration = time.perf_counter() - t0
            trial.set_user_attr("duration_sec", duration)
            trial.set_user_attr("config_dict", config_to_dict(cfg))

            best_obj = obj if best_obj is None else min(best_obj, obj)
            progress.update(
                task_id,
                advance=1,
                detail=format_hpo_detail(
                    method,
                    trial_idx,
                    n_trials,
                    last_objective=obj,
                    best_objective=best_obj,
                ),
            )
            return obj

        study.optimize(_objective, n_trials=n_trials)

    for trial in study.trials:
        row: dict = {
            "trial_number": trial.number,
            "state": trial.state.name,
            "objective": round(float(trial.value), 6)
            if trial.value is not None
            else None,
            "duration_sec": round(float(trial.user_attrs.get("duration_sec", 0.0)), 6),
        }
        row.update(trial.params)
        trial_rows.append(row)

    best_trial = study.best_trial
    if best_trial.value is None:
        raise RuntimeError(f"Best trial for {method} has no objective value.")
    best_cfg_dict = best_trial.user_attrs["config_dict"]
    method_result = {
        "best_objective": round(float(best_trial.value), 6),
        "best_trial_number": int(best_trial.number),
        "config": best_cfg_dict,
    }
    return method_result, trial_rows


def save_hpo_results(
    results: dict,
    trials_by_method: dict[str, list[dict]],
    output_dir: str | Path = "results",
) -> Path:
    """Persist hpo_best_configs.json and per-method trial history CSVs."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    json_path = out / "hpo_best_configs.json"
    json_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    csv_names = {
        METHOD_PURE: "hpo_trials_pure_ga.csv",
        METHOD_MEMETIC: "hpo_trials_memetic_ga.csv",
    }
    for method, rows in trials_by_method.items():
        if method in csv_names and rows:
            save_csv(rows, out / csv_names[method])

    return json_path


def load_tuned_configs(
    path: str | Path,
    *,
    require_both: bool = False,
) -> dict[str, GAConfig]:
    """Load and validate tuned GAConfig objects from an hpo_best_configs.json file."""
    cfg_path = Path(path)
    if not cfg_path.is_file():
        raise FileNotFoundError(f"Tuned config file not found: {cfg_path}")

    try:
        payload = json.loads(cfg_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON in tuned config file {cfg_path}: {exc}"
        ) from exc

    if not isinstance(payload, dict):
        raise TypeError(f"Tuned config root must be a JSON object in {cfg_path}")

    loaded: dict[str, GAConfig] = {}
    for method in VALID_METHODS:
        if method in payload:
            entry = payload[method]
            if not isinstance(entry, dict) or "config" not in entry:
                raise ValueError(
                    f"Invalid {method} entry in {cfg_path}: missing 'config'"
                )
            loaded[method] = _validate_and_build_config(method, entry["config"])

    if not loaded:
        raise ValueError(
            f"Tuned config {cfg_path} does not contain Pure_GA or Memetic_GA entries."
        )
    if require_both and set(loaded.keys()) != set(VALID_METHODS):
        missing = sorted(set(VALID_METHODS) - set(loaded.keys()))
        raise ValueError(
            f"Tuned config {cfg_path} must contain both Pure_GA and Memetic_GA; missing {missing}"
        )

    return loaded


def run_hpo_suite(
    instances: list[CVRPInstance],
    seeds: list[int],
    *,
    methods: tuple[str, ...] = VALID_METHODS,
    n_trials: int = 30,
    generations: int = 100,
    hpo_seed: int = 42,
    output_dir: str | Path = "results",
    show_progress: bool = True,
    console: Console | None = None,
) -> dict:
    """Run HPO for the requested methods, export artifacts, and render summary."""
    active_console = console or Console()
    baselines = compute_greedy_baselines(instances)

    results: dict = {
        "metadata": {
            "instances": [inst.name for inst in instances],
            "seeds": [int(s) for s in seeds],
            "n_trials": int(n_trials),
            "generations": int(generations),
            "hpo_seed": int(hpo_seed),
        }
    }
    trials_by_method: dict[str, list[dict]] = {}

    for method in methods:
        method_res, trial_rows = optimize_ga(
            method,
            instances,
            seeds,
            n_trials=n_trials,
            generations=generations,
            hpo_seed=hpo_seed,
            greedy_baselines=baselines,
            show_progress=show_progress,
            console=active_console,
        )
        results[method] = method_res
        trials_by_method[method] = trial_rows

    save_hpo_results(results, trials_by_method, output_dir)
    if show_progress:
        render_hpo_summary(active_console, results)
    return results


def _resolve_tuning_instances(instance_names: list[str] | None) -> list[CVRPInstance]:
    """Resolve tuning instances from CLI names or default CVRPLIB training set."""
    cvrplib = [
        load_cvrplib(Path("data/cvrplib") / name) for name in DEFAULT_CVRPLIB_NAMES
    ]
    if not instance_names:
        return cvrplib

    available: dict[str, CVRPInstance] = {inst.name: inst for inst in cvrplib}
    recife_dir = Path("data/recife_ubs")
    if recife_dir.is_dir():
        recife = load_recife(recife_dir)
        available[recife.name] = recife

    resolved: list[CVRPInstance] = []
    for name in instance_names:
        if name in available:
            resolved.append(available[name])
        elif Path(name).is_file():
            resolved.append(load_cvrplib(name))
        else:
            raise ValueError(
                f"Unknown tuning instance {name!r}; available: {sorted(available)}"
            )
    return resolved


def build_arg_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser for standalone hyperparameter optimization."""
    parser = argparse.ArgumentParser(
        description="Run Optuna TPE hyperparameter optimization for Pure GA and Memetic GA."
    )
    parser.add_argument(
        "--method",
        choices=["pure", "memetic", "both"],
        default="both",
        help="Which GA variant(s) to tune.",
    )
    parser.add_argument(
        "--trials", type=int, default=30, help="Optuna trials per method."
    )
    parser.add_argument(
        "--seeds",
        type=int,
        default=3,
        help="Number of evaluation seeds (1..seeds) per trial.",
    )
    parser.add_argument(
        "--generations",
        type=int,
        default=100,
        help="Fixed generation budget per evaluation.",
    )
    parser.add_argument(
        "--hpo-seed", type=int, default=42, help="Master seed for Optuna TPESampler."
    )
    parser.add_argument(
        "--instances",
        nargs="+",
        default=None,
        help="Optional instance names or .vrp paths (default: A-n32-k5 A-n45-k6 A-n60-k9).",
    )
    parser.add_argument("--output-dir", type=str, default="results")
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable live rich progress bars and summary tables.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_arg_parser().parse_args(argv)
    show_progress = not args.no_progress
    console = Console()

    method_map = {
        "pure": (METHOD_PURE,),
        "memetic": (METHOD_MEMETIC,),
        "both": VALID_METHODS,
    }
    instances = _resolve_tuning_instances(args.instances)
    seeds = list(range(1, args.seeds + 1))

    run_hpo_suite(
        instances,
        seeds,
        methods=method_map[args.method],
        n_trials=args.trials,
        generations=args.generations,
        hpo_seed=args.hpo_seed,
        output_dir=args.output_dir,
        show_progress=show_progress,
        console=console,
    )


if __name__ == "__main__":
    main()
