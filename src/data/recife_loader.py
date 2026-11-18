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
    latlon = np.array([[n["lat"], n["lon"]] for n in nodes], dtype=np.float64)
    demands = np.array([int(n["demand"]) for n in nodes], dtype=np.int64)
    node_names = [str(n["name"]) for n in nodes]
    capacity = int(payload["capacity"])
    depot = int(payload.get("depot", 0))
    dist_matrix = np.load(road_path)

    return CVRPInstance(
        name=f"{payload.get('name', 'Recife-UBS')}-road",
        distance_matrix=dist_matrix,
        demands=demands,
        capacity=capacity,
        depot=depot,
        latlon=latlon,
        node_names=node_names,
    )
