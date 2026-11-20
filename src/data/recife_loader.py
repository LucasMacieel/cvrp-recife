"""Offline loader for the Recife/PE UBS & USF geographic CVRP scenario."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from src.data.models import CVRPInstance


def load_recife(
    data_dir: str | Path = "data/recife_ubs",
) -> CVRPInstance:
    """Load the static Recife/PE road-network CVRP instance offline.

    Args:
        data_dir: Directory containing recife_ubs.json and
            distance_matrix_road.npy.

    Returns:
        Validated CVRPInstance.
    """
    base = Path(data_dir)
    json_path = base / "recife_ubs.json"
    if not json_path.exists():
        raise FileNotFoundError(f"Recife metadata file not found: {json_path}")

    road_path = base / "distance_matrix_road.npy"
    if not road_path.exists():
        raise FileNotFoundError(f"Recife road distance matrix not found: {road_path}")

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    nodes = payload["nodes"]
    seen_ids: set[str] = set()
    duplicate_ids: list[str] = []
    for node in nodes:
        if "id" in node and node["id"] is not None:
            node_id = str(node["id"])
            if node_id in seen_ids and node_id not in duplicate_ids:
                duplicate_ids.append(node_id)
            seen_ids.add(node_id)
    if duplicate_ids:
        raise ValueError(
            f"Duplicate node id(s) found in {json_path}: {', '.join(duplicate_ids)}"
        )
    latlon = np.array([[n["lat"], n["lon"]] for n in nodes], dtype=np.float64)
    demands = np.array([int(n["demand"]) for n in nodes], dtype=np.int64)
    node_names = [str(n["name"]) for n in nodes]
    capacity = int(payload["capacity"])
    depot = int(payload.get("depot", 0))
    raw_optimal = payload.get("optimal_value")
    optimal_value = float(raw_optimal) if raw_optimal is not None else None
    dist_matrix = np.load(road_path)

    return CVRPInstance(
        name=f"{payload.get('name', 'Recife-UBS')}-road",
        distance_matrix=dist_matrix,
        demands=demands,
        capacity=capacity,
        depot=depot,
        latlon=latlon,
        optimal_value=optimal_value,
        node_names=node_names,
    )
