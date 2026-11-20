"""Analytical plots (convergence curves and comparative boxplots) for CVRP."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


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
