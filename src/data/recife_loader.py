"""Offline loader for the Recife/PE UBS & USF geographic CVRP scenario."""

from __future__ import annotations

import json
from pathlib import Path
import numpy as np

from src.data.models import CVRPInstance


def compute_haversine_matrix(latlon: np.ndarray) -> np.ndarray:
    """Compute pairwise Haversine distances in kilometers for (N, 2) lat/lon."""
    coords = np.asarray(latlon, dtype=np.float64)
    if coords.ndim != 2 or coords.shape[1] != 2:
        raise ValueError(f"latlon must have shape (N, 2), got {coords.shape}")

    rad = np.radians(coords)
    lat = rad[:, 0:1]
    lon = rad[:, 1:2]
    dlat = lat - lat.T
    dlon = lon - lon.T
    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat) * np.cos(lat.T) * np.sin(dlon / 2.0) ** 2
    c = 2.0 * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))
    dist = 6371.0088 * c
    np.fill_diagonal(dist, 0.0)
    return dist


def load_recife(
    data_dir: str | Path = "data/recife_ubs",
    *,
    mode: str = "road",
) -> CVRPInstance:
    """Load the static Recife/PE CVRP instance offline.

    Args:
        data_dir: Directory containing recife_ubs.json and optionally
            distance_matrix_road.npy.
        mode: Distance mode, either 'road' (precomputed OSRM matrix with
            Haversine fallback if absent) or 'haversine' (geodesic km).

    Returns:
        Validated CVRPInstance.
    """
    if mode not in {"road", "haversine"}:
        raise ValueError(f"Unsupported Recife distance mode {mode!r}; use 'road' or 'haversine'")

    base = Path(data_dir)
    json_path = base / "recife_ubs.json"
    if not json_path.exists():
        raise FileNotFoundError(f"Recife metadata file not found: {json_path}")

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    nodes = payload["nodes"]
    latlon = np.array([[n["lat"], n["lon"]] for n in nodes], dtype=np.float64)
    demands = np.array([int(n["demand"]) for n in nodes], dtype=np.int64)
    node_names = [str(n["name"]) for n in nodes]
    capacity = int(payload["capacity"])
    depot = int(payload.get("depot", 0))

    road_path = base / "distance_matrix_road.npy"
    if mode == "road" and road_path.exists():
        dist_matrix = np.load(road_path)
    else:
        dist_matrix = compute_haversine_matrix(latlon)

    return CVRPInstance(
        name=f"{payload.get('name', 'Recife-UBS')}-{mode}",
        distance_matrix=dist_matrix,
        demands=demands,
        capacity=capacity,
        depot=depot,
        latlon=latlon,
        node_names=node_names,
    )
