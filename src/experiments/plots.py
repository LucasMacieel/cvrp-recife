"""Analytical plots (convergence curves, comparative boxplots, and best-solution routes) for CVRP."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from src.data.models import CVRPInstance
from src.experiments.map_recife import _fetch_osrm_route_geometry


def plot_convergence_curves(
    histories: dict[str, dict[str, list[list[float]]]],
    output_dir: str | Path = "results",
    *,
    prefix: str = "convergence",
) -> list[Path]:
    """Plot mean +/- std convergence curves per instance and save as PNG."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []

    for inst_name, methods in histories.items():
        if not any(methods.values()):
            continue
        fig, ax = plt.subplots(figsize=(8, 5))
        for label, runs in methods.items():
            if not runs:
                continue
            arr = np.asarray(runs, dtype=np.float64)
            gens = np.arange(arr.shape[1])
            mean = np.mean(arr, axis=0)
            std = (
                np.std(arr, axis=0, ddof=1) if arr.shape[0] > 1 else np.zeros_like(mean)
            )
            ax.plot(gens, mean, label=label, linewidth=2.0)
            ax.fill_between(gens, mean - std, mean + std, alpha=0.2)

        ax.set_title(f"Convergence — {inst_name}")
        ax.set_xlabel("Generation")
        ax.set_ylabel("Total Distance")
        ax.grid(True, linestyle="--", alpha=0.4)
        ax.legend()
        fig.tight_layout()

        path = out / f"{prefix}_{inst_name}.png"
        fig.savefig(path, dpi=150)
        plt.close(fig)
        saved.append(path)

    return saved


def plot_comparative_boxplots(
    rows: list[dict],
    output_dir: str | Path = "results",
) -> list[Path]:
    """Plot comparative boxplots (Pure GA vs. Memetic GA) with Greedy/Optimal lines."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []

    by_inst: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    opt_by_inst: dict[str, float | None] = {}
    for row in rows:
        inst = str(row["instance"])
        method = str(row["method"])
        by_inst[inst][method].append(float(row["distance"]))
        raw_opt = row.get("optimal_value")
        if raw_opt not in (None, "", "None"):
            opt_by_inst[inst] = float(raw_opt)

    for inst_name, methods in by_inst.items():
        pure = methods.get("Pure_GA", [])
        mem = methods.get("Memetic_GA", [])
        if not pure and not mem:
            continue

        fig, ax = plt.subplots(figsize=(6.5, 5))
        data = []
        labels = []
        if pure:
            data.append(pure)
            labels.append("Pure GA")
        if mem:
            data.append(mem)
            labels.append("Memetic GA")

        ax.boxplot(data, tick_labels=labels, patch_artist=True)
        if "Greedy" in methods:
            ax.axhline(
                methods["Greedy"][0],
                color="tab:orange",
                linestyle="--",
                linewidth=1.5,
                label=f"Greedy ({methods['Greedy'][0]:.1f})",
            )
        opt_v = opt_by_inst.get(inst_name)
        if opt_v is not None:
            ax.axhline(
                opt_v,
                color="tab:green",
                linestyle=":",
                linewidth=1.8,
                label=f"Optimal ({opt_v:.1f})",
            )

        ax.set_title(f"Distance Distribution — {inst_name}")
        ax.set_ylabel("Total Distance")
        ax.grid(True, axis="y", linestyle="--", alpha=0.4)
        if ax.get_legend_handles_labels()[1]:
            ax.legend()
        fig.tight_layout()

        path = out / f"boxplot_{inst_name}.png"
        fig.savefig(path, dpi=150)
        plt.close(fig)
        saved.append(path)

    return saved


def plot_best_solution_routes(
    instance: CVRPInstance,
    routes: Sequence[Sequence[int]],
    distance: float,
    output_path: str | Path,
    *,
    method_label: str = "Memetic GA",
    use_osrm: bool = True,
) -> Path:
    """Plot a static Matplotlib visualization of CVRP routes (road-snapped when latlon+OSRM)."""
    is_geo = instance.latlon is not None
    if is_geo:
        coords_arr = instance.latlon
        assert coords_arr is not None
        xs_all = coords_arr[:, 1]  # longitude
        ys_all = coords_arr[:, 0]  # latitude
    elif instance.coords is not None:
        coords_arr = instance.coords
        xs_all = coords_arr[:, 0]
        ys_all = coords_arr[:, 1]
    else:
        raise ValueError(
            "Instance must provide either latlon or coords to plot solution routes."
        )

    depot = instance.depot
    depot_x = float(xs_all[depot])
    depot_y = float(ys_all[depot])

    fig, ax = plt.subplots(figsize=(7.5, 6.2))
    cmap = plt.get_cmap("tab10")

    for v_idx, route in enumerate(routes):
        color = cmap(v_idx % 10)
        if is_geo:
            waypoints = [[depot_y, depot_x]]
            for node in route:
                waypoints.append([float(ys_all[node]), float(xs_all[node])])
            waypoints.append([depot_y, depot_x])

            poly = waypoints
            if use_osrm and route:
                road_coords = _fetch_osrm_route_geometry(waypoints)
                if road_coords is not None:
                    poly = road_coords
            line_xs = [pt[1] for pt in poly]
            line_ys = [pt[0] for pt in poly]
        else:
            node_seq = [depot, *route, depot]
            line_xs = [float(xs_all[n]) for n in node_seq]
            line_ys = [float(ys_all[n]) for n in node_seq]

        ax.plot(
            line_xs,
            line_ys,
            color=color,
            linewidth=1.8,
            alpha=0.9,
            label=f"Route {v_idx + 1} ({len(route)} units)",
            zorder=3,
        )
        if route:
            cust_xs = [float(xs_all[n]) for n in route]
            cust_ys = [float(ys_all[n]) for n in route]
            ax.scatter(
                cust_xs,
                cust_ys,
                color=color,
                edgecolors="black",
                linewidths=0.8,
                s=55,
                zorder=4,
            )

    depot_label = "Depot"
    if instance.node_names:
        raw_name = instance.node_names[depot]
        if "CAF Recife" in raw_name:
            depot_label = "Depot (CAF Recife)"
        else:
            depot_label = f"Depot ({raw_name})"

    ax.scatter(
        [depot_x],
        [depot_y],
        marker="*",
        color="red",
        edgecolors="black",
        linewidths=1.0,
        s=300,
        label=depot_label,
        zorder=6,
    )

    if is_geo:
        title = (
            f"Best {method_label} Solution — {instance.name} "
            f"({distance:.2f} km, {len(routes)} routes)"
        )
        ax.set_xlabel("Longitude (°)")
        ax.set_ylabel("Latitude (°)")
    else:
        title = (
            f"Best {method_label} Solution — {instance.name} "
            f"({distance:.1f}, {len(routes)} routes)"
        )
        ax.set_xlabel("X")
        ax.set_ylabel("Y")

    ax.set_title(title, fontweight="bold")
    ax.set_aspect("equal", adjustable="datalim")
    ax.grid(True, linestyle="--", alpha=0.4)
    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.12),
        ncol=3,
        frameon=True,
    )

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return out
