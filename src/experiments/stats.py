"""Statistical aggregation and non-parametric hypothesis tests for CVRP experiments."""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats


def compute_gap_pct(distance: float, optimal_value: float | None) -> float | None:
    """Compute percentage gap: ((distance - optimal) / optimal) * 100."""
    if optimal_value is None or optimal_value <= 0:
        return None
    return ((float(distance) - float(optimal_value)) / float(optimal_value)) * 100.0


def aggregate_results(rows: list[dict]) -> list[dict]:
    """Aggregate raw experiment rows by (instance, method, crossover, mutation)."""
    grouped: dict[tuple[str, str, str, str], list[dict]] = defaultdict(list)
    for row in rows:
        key = (
            str(row["instance"]),
            str(row["method"]),
            str(row.get("crossover", "")),
            str(row.get("mutation", "")),
        )
        grouped[key].append(row)

    summary: list[dict] = []
    for (inst_name, method, cx, mut), items in grouped.items():
        dists = np.array([float(x["distance"]) for x in items], dtype=np.float64)
        times = np.array([float(x["runtime_sec"]) for x in items], dtype=np.float64)
        vehs = np.array([int(x["num_vehicles"]) for x in items], dtype=np.float64)

        raw_opt = items[0].get("optimal_value")
        opt_val = float(raw_opt) if raw_opt not in (None, "", "None") else None

        mean_dist = float(np.mean(dists))
        best_dist = float(np.min(dists))
        summary.append(
            {
                "instance": inst_name,
                "method": method,
                "crossover": cx,
                "mutation": mut,
                "n_runs": len(items),
                "mean_distance": mean_dist,
                "std_distance": float(np.std(dists, ddof=1)) if len(dists) > 1 else 0.0,
                "best_distance": best_dist,
                "worst_distance": float(np.max(dists)),
                "optimal_value": opt_val,
                "mean_gap_pct": compute_gap_pct(mean_dist, opt_val),
                "best_gap_pct": compute_gap_pct(best_dist, opt_val),
                "mean_vehicles": float(np.mean(vehs)),
                "mean_runtime_sec": float(np.mean(times)),
            }
        )
    return summary


def compare_pure_vs_memetic(rows: list[dict]) -> list[dict]:
    """Run Wilcoxon signed-rank and Mann-Whitney U tests between Pure GA and Memetic GA."""
    by_inst_method: dict[tuple[str, str], dict[int, float]] = defaultdict(dict)
    for row in rows:
        method = str(row["method"])
        if method in {"Pure_GA", "Memetic_GA"}:
            by_inst_method[(str(row["instance"]), method)][int(row["seed"])] = float(
                row["distance"]
            )

    instances = sorted({inst for inst, _ in by_inst_method})
    comparisons: list[dict] = []

    for inst in instances:
        pure_map = by_inst_method.get((inst, "Pure_GA"), {})
        mem_map = by_inst_method.get((inst, "Memetic_GA"), {})
        common_seeds = sorted(set(pure_map.keys()) & set(mem_map.keys()))
        if not common_seeds:
            continue

        pure_vals = np.array([pure_map[s] for s in common_seeds], dtype=np.float64)
        mem_vals = np.array([mem_map[s] for s in common_seeds], dtype=np.float64)

        mw_stat, mw_p = stats.mannwhitneyu(mem_vals, pure_vals, alternative="two-sided")

        diffs = pure_vals - mem_vals
        if np.allclose(diffs, 0.0):
            wx_stat, wx_p = 0.0, 1.0
        else:
            wx_stat, wx_p = stats.wilcoxon(mem_vals, pure_vals, alternative="two-sided")

        comparisons.append(
            {
                "instance": inst,
                "n_pairs": len(common_seeds),
                "pure_mean": float(np.mean(pure_vals)),
                "memetic_mean": float(np.mean(mem_vals)),
                "improvement_pct": float(
                    ((np.mean(pure_vals) - np.mean(mem_vals)) / np.mean(pure_vals)) * 100.0
                ),
                "mann_whitney_u": float(mw_stat),
                "mann_whitney_p": float(mw_p),
                "wilcoxon_stat": float(wx_stat),
                "wilcoxon_p": float(wx_p),
                "significant_005": bool(wx_p < 0.05),
            }
        )
    return comparisons


def save_csv(rows: list[dict], path: str | Path) -> None:
    """Write a list of uniform dictionaries to CSV."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        out.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
