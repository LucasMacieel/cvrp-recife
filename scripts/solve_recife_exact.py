"""Offline exact ACVRP solver for the Recife/PE road-network scenario.

Uses Google OR-Tools CP-SAT (``AddMultipleCircuit`` + exact cumulative load
propagation) from the optional ``exact`` dependency group to compute a
mathematically proven global optimum for ``Recife-UBS-40-road`` and persist an
audit certificate into ``data/recife_ubs/recife_ubs.json``.

Usage:
    uv run --group exact scripts/solve_recife_exact.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import import_module, metadata
from pathlib import Path
from typing import Any

import numpy as np

# Ensure repository root is importable when invoked as a script.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.data.cvrplib_loader import load_cvrplib
from src.data.models import CVRPInstance
from src.data.recife_loader import load_recife
from src.solver.decoder import total_distance, validate_routes

DISTANCE_TOLERANCE = 1e-4
SELF_CHECK_INSTANCE = _REPO_ROOT / "data/cvrplib/A-n32-k5.vrp"
SELF_CHECK_EXPECTED_OPT = 784.0


@dataclass(frozen=True)
class ExactSolveResult:
    """Normalized outcome of an exact CVRP/ACVRP solver invocation."""

    status: str
    optimal_proven: bool
    objective: float | None
    best_lb: float | None
    routes: list[list[int]]
    runtime_seconds: float
    solver: str
    solver_version: str


def compute_file_sha256(path: Path) -> str:
    """Return the lowercase hexadecimal SHA-256 digest of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _get_ortools_version() -> str:
    try:
        return metadata.version("ortools")
    except metadata.PackageNotFoundError:
        return "unknown"


def _select_integer_scale(dist_matrix: np.ndarray) -> int:
    """Choose the smallest power-of-10 factor making all distances exact integers."""
    for power in range(7):
        scale = 10**power
        scaled = dist_matrix * scale
        if np.allclose(scaled, np.round(scaled), rtol=0.0, atol=1e-6):
            return scale
    return 10_000


def _extract_routes_from_arcs(
    arcs: dict[int, list[int]],
    depot: int,
) -> list[list[int]]:
    """Extract ordered customer routes starting at ``depot`` from active arcs."""
    routes: list[list[int]] = []
    for nxt in arcs.get(depot, []):
        route: list[int] = []
        cur = nxt
        visited: set[int] = {depot}
        while cur != depot and cur not in visited:
            visited.add(cur)
            route.append(cur)
            successors = arcs.get(cur, [])
            if not successors:
                break
            cur = successors[0]
        if route:
            routes.append(route)
    return routes


def solve_instance_exact(
    instance: CVRPInstance,
    *,
    time_limit: float = 1800.0,
    upper_bound: float | None = None,
) -> ExactSolveResult:
    """Solve a directed CVRP/ACVRP instance to proven optimality via OR-Tools CP-SAT."""
    try:
        cp_model = import_module("ortools.sat.python.cp_model")
    except ImportError as exc:
        raise RuntimeError(
            "ortools is not installed in the active environment. "
            "Run with `uv run --group exact scripts/solve_recife_exact.py`."
        ) from exc

    n = instance.num_nodes
    depot = int(instance.depot)
    customers = instance.customers
    demands = [int(d) for d in instance.demands]
    capacity = int(instance.capacity)
    dist_mat = instance.distance_matrix

    # Map depot -> 0 for CP-SAT AddMultipleCircuit (which anchors all cycles at node 0).
    orig_to_model = {depot: 0}
    for idx, cust in enumerate(customers, start=1):
        orig_to_model[cust] = idx

    scale = _select_integer_scale(dist_mat)
    dist_int = np.rint(dist_mat * scale).astype(np.int64)

    model = cp_model.CpModel()
    x: dict[tuple[int, int], Any] = {}
    circuit_arcs: list[tuple[int, int, Any]] = []

    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            if i != depot and j != depot and demands[i] + demands[j] > capacity:
                continue
            var = model.new_bool_var(f"x_{i}_{j}")
            x[i, j] = var
            circuit_arcs.append((orig_to_model[i], orig_to_model[j], var))

    # Built-in global constraint enforcing elementary customer routes through depot
    model.add_multiple_circuit(circuit_arcs)

    # Exact cumulative route-load propagation along active directed arcs
    load = {c: model.new_int_var(demands[c], capacity, f"load_{c}") for c in customers}
    for (i, j), var in x.items():
        if i == depot and j != depot:
            model.add(load[j] == demands[j]).only_enforce_if(var)
        elif i != depot and j != depot:
            model.add(load[j] == load[i] + demands[j]).only_enforce_if(var)

    # Valid minimum fleet lower bound (unconstrained upper bound on vehicles)
    k_min = math.ceil(sum(demands[c] for c in customers) / capacity)
    model.add(sum(x[depot, c] for c in customers if (depot, c) in x) >= k_min)

    # Upfront 2-node subtour cuts to tighten LP relaxation
    for idx_a, i in enumerate(customers):
        for j in customers[idx_a + 1 :]:
            if (i, j) in x and (j, i) in x:
                model.add(x[i, j] + x[j, i] <= 1)

    obj_expr = sum(int(dist_int[i, j]) * var for (i, j), var in x.items())
    if upper_bound is not None:
        model.add(obj_expr <= math.ceil((upper_bound + 1e-2) * scale))
    model.minimize(obj_expr)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(time_limit)
    solver.parameters.num_search_workers = min(8, os.cpu_count() or 1)

    status_enum = solver.solve(model)
    optimal_proven = status_enum == cp_model.OPTIMAL
    status_name = str(solver.status_name(status_enum)).lower()

    routes: list[list[int]] = []
    objective: float | None = None
    if status_enum in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        objective = float(solver.objective_value) / scale
        arcs: dict[int, list[int]] = {i: [] for i in range(n)}
        for (i, j), var in x.items():
            if solver.value(var) == 1:
                arcs[i].append(j)
        routes = _extract_routes_from_arcs(arcs, depot)

    best_lb = float(solver.best_objective_bound) / scale
    runtime_seconds = float(solver.wall_time)

    return ExactSolveResult(
        status="optimal" if optimal_proven else status_name,
        optimal_proven=optimal_proven,
        objective=objective,
        best_lb=best_lb,
        routes=routes,
        runtime_seconds=runtime_seconds,
        solver="OR-Tools CP-SAT (AddMultipleCircuit)",
        solver_version=_get_ortools_version(),
    )


def verify_and_build_certificate(
    instance: CVRPInstance,
    result: ExactSolveResult,
    matrix_sha256: str,
    *,
    tolerance: float = DISTANCE_TOLERANCE,
) -> tuple[float, dict[str, Any]]:
    """Independently verify an optimal result and construct its provenance certificate."""
    if not result.optimal_proven:
        raise ValueError(
            f"Cannot certify optimal solution: solver status is '{result.status}' "
            f"(objective={result.objective}, best_lb={result.best_lb})."
        )
    if result.objective is None:
        raise ValueError(
            "Solver reported optimal_proven=True without an objective value."
        )

    validate_routes(result.routes, instance)
    recomputed = float(
        total_distance(result.routes, instance.distance_matrix, instance.depot)
    )
    diff = abs(recomputed - float(result.objective))
    if diff > tolerance:
        raise ValueError(
            f"Distance mismatch between solver objective ({result.objective:.6f}) "
            f"and recomputed total_distance ({recomputed:.6f}): diff={diff:.6g} > {tolerance}"
        )
    if result.best_lb is None:
        raise ValueError(
            "Solver reported optimal_proven=True without a dual lower bound."
        )
    lb_gap = abs(recomputed - float(result.best_lb))
    if lb_gap > tolerance:
        raise ValueError(
            f"Non-zero dual/primal gap: recomputed={recomputed:.6f}, "
            f"best_lb={result.best_lb:.6f}, gap={lb_gap:.6g} > {tolerance}"
        )

    certificate: dict[str, Any] = {
        "status": "optimal",
        "solver": result.solver,
        "solver_version": result.solver_version,
        "distance": recomputed,
        "solver_objective": float(result.objective),
        "dual_lower_bound": float(result.best_lb),
        "gap_pct": 0.0,
        "num_vehicles": len(result.routes),
        "routes": [list(map(int, r)) for r in result.routes],
        "runtime_seconds": round(float(result.runtime_seconds), 4),
        "distance_matrix_sha256": matrix_sha256,
        "solved_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    return recomputed, certificate


def persist_exact_certificate(
    json_path: Path,
    optimal_value: float,
    certificate: dict[str, Any],
) -> None:
    """Persist certified ``optimal_value`` and ``exact_solution`` into ``recife_ubs.json``."""
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    payload["optimal_value"] = float(optimal_value)
    payload["exact_solution"] = certificate
    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def run_exact_workflow(
    *,
    data_dir: Path,
    time_limit: float = 1800.0,
    upper_bound: float | None = None,
    skip_self_check: bool = False,
    dry_run: bool = False,
    solver_fn: Callable[..., ExactSolveResult] = solve_instance_exact,
) -> int:
    """Execute optional A-n32-k5 self-check, solve Recife ACVRP, verify, and persist."""
    if not skip_self_check:
        self_inst = load_cvrplib(SELF_CHECK_INSTANCE)
        self_res = solver_fn(self_inst, time_limit=min(time_limit, 300.0))
        if not self_res.optimal_proven or self_res.objective is None:
            print(
                f"[ERROR] Self-check on {self_inst.name} did not prove optimality "
                f"(status={self_res.status}, obj={self_res.objective}, lb={self_res.best_lb}).",
                file=sys.stderr,
            )
            return 1
        validate_routes(self_res.routes, self_inst)
        self_dist = total_distance(
            self_res.routes, self_inst.distance_matrix, self_inst.depot
        )
        if (
            abs(self_dist - SELF_CHECK_EXPECTED_OPT) > DISTANCE_TOLERANCE
            or abs(self_dist - float(self_res.objective)) > DISTANCE_TOLERANCE
        ):
            print(
                f"[ERROR] Self-check on {self_inst.name} produced distance={self_dist:.6f} "
                f"(solver_obj={self_res.objective:.6f}), expected {SELF_CHECK_EXPECTED_OPT:.1f}.",
                file=sys.stderr,
            )
            return 1
        print(
            f"[SELF-CHECK OK] {self_inst.name}: optimal={self_dist:.4f} "
            f"(vehicles={len(self_res.routes)}, time={self_res.runtime_seconds:.2f}s)"
        )

    recife = load_recife(data_dir)
    matrix_path = data_dir / "distance_matrix_road.npy"
    json_path = data_dir / "recife_ubs.json"
    matrix_sha256 = compute_file_sha256(matrix_path)

    res = solver_fn(recife, time_limit=time_limit, upper_bound=upper_bound)
    if not res.optimal_proven:
        print(
            f"[UNPROVEN] {recife.name}: status={res.status}, "
            f"best_feasible={res.objective}, dual_lb={res.best_lb}, "
            f"time={res.runtime_seconds:.2f}s. "
            "recife_ubs.json was NOT modified.",
            file=sys.stderr,
        )
        return 1

    optimal_value, certificate = verify_and_build_certificate(
        recife, res, matrix_sha256
    )

    if dry_run:
        print(
            f"[DRY-RUN OK] {recife.name}: optimal={optimal_value:.4f} km "
            f"(lb={certificate['dual_lower_bound']:.4f}, "
            f"vehicles={certificate['num_vehicles']}, "
            f"time={certificate['runtime_seconds']:.2f}s, "
            f"sha256={matrix_sha256[:12]}...)"
        )
        return 0

    persist_exact_certificate(json_path, optimal_value, certificate)
    print(
        f"[CERTIFIED] {recife.name}: optimal_value={optimal_value:.4f} km "
        f"(vehicles={certificate['num_vehicles']}, "
        f"time={certificate['runtime_seconds']:.2f}s) saved to {json_path}"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser for ``solve_recife_exact.py``."""
    parser = argparse.ArgumentParser(
        description=(
            "Compute and certify the global optimum for Recife-UBS-40-road "
            "using OR-Tools CP-SAT (optional `exact` dependency group)."
        )
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data/recife_ubs"),
        help="Directory containing recife_ubs.json and distance_matrix_road.npy (default: data/recife_ubs).",
    )
    parser.add_argument(
        "--time-limit",
        type=float,
        default=1800.0,
        help="Solver time limit in seconds (default: 1800).",
    )
    parser.add_argument(
        "--upper-bound",
        type=float,
        default=None,
        help="Optional primal upper-bound cutoff in km (a +1e-2 safety margin is added automatically).",
    )
    parser.add_argument(
        "--skip-self-check",
        action="store_true",
        help="Skip the A-n32-k5 == 784.0 ground-truth verification before solving Recife.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solve and verify without modifying recife_ubs.json.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    args = build_parser().parse_args(argv)
    return run_exact_workflow(
        data_dir=args.data_dir,
        time_limit=args.time_limit,
        upper_bound=args.upper_bound,
        skip_self_check=args.skip_self_check,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())
