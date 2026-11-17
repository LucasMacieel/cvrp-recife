"""Loader for standard CVRPLIB (.vrp) instances with EUC_2D coordinates."""

from __future__ import annotations

import re
from pathlib import Path
import numpy as np

from src.data.models import CVRPInstance

_OPT_VALUE_RE = re.compile(
    r"(?:Optimal|Best)\s+value\s*:\s*([0-9]+(?:\.[0-9]+)?)",
    re.IGNORECASE,
)


def load_cvrplib(
    path: str | Path,
    *,
    round_distances: bool = True,
) -> CVRPInstance:
    """Parse a CVRPLIB .vrp file (EUC_2D) into a validated CVRPInstance.

    Args:
        path: Path to the .vrp file.
        round_distances: Whether to apply TSPLIB EUC_2D nearest-integer rounding
            (floor(d + 0.5)) so distances match published CVRPLIB optima.

    Returns:
        Validated CVRPInstance.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"CVRPLIB file not found: {file_path}")

    text = file_path.read_text(encoding="utf-8", errors="replace")
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    name = file_path.stem
    dimension: int | None = None
    capacity: int | None = None
    edge_weight_type: str | None = None
    optimal_value: float | None = None

    coords_map: dict[int, tuple[float, float]] = {}
    demands_map: dict[int, int] = {}
    depot_ids: list[int] = []

    section: str | None = None
    for line in lines:
        upper = line.upper()
        if upper == "EOF":
            break
        if upper.startswith("NODE_COORD_SECTION"):
            section = "NODE_COORD"
            continue
        if upper.startswith("DEMAND_SECTION"):
            section = "DEMAND"
            continue
        if upper.startswith("DEPOT_SECTION"):
            section = "DEPOT"
            continue

        if section is None:
            if ":" in line:
                key, val = line.split(":", 1)
                key = key.strip().upper()
                val = val.strip()
                if key == "NAME":
                    name = val
                elif key == "COMMENT":
                    match = _OPT_VALUE_RE.search(val)
                    if match:
                        optimal_value = float(match.group(1))
                elif key == "DIMENSION":
                    dimension = int(val)
                elif key == "CAPACITY":
                    capacity = int(val)
                elif key == "EDGE_WEIGHT_TYPE":
                    edge_weight_type = val.upper()
            continue

        parts = line.split()
        if section == "NODE_COORD":
            if len(parts) < 3:
                raise ValueError(f"Malformed NODE_COORD_SECTION line: {line!r}")
            node_id = int(parts[0])
            coords_map[node_id] = (float(parts[1]), float(parts[2]))
        elif section == "DEMAND":
            if len(parts) < 2:
                raise ValueError(f"Malformed DEMAND_SECTION line: {line!r}")
            node_id = int(parts[0])
            demands_map[node_id] = int(parts[1])
        elif section == "DEPOT":
            dep_id = int(parts[0])
            if dep_id == -1:
                section = None
            else:
                depot_ids.append(dep_id)

    if dimension is None or capacity is None:
        raise ValueError(f"Missing DIMENSION or CAPACITY in {file_path}")
    if edge_weight_type != "EUC_2D":
        raise ValueError(
            f"Unsupported EDGE_WEIGHT_TYPE {edge_weight_type!r} in {file_path}; expected 'EUC_2D'"
        )
    if len(coords_map) != dimension:
        raise ValueError(
            f"Expected {dimension} coordinates in NODE_COORD_SECTION, found {len(coords_map)}"
        )
    if len(demands_map) != dimension:
        raise ValueError(
            f"Expected {dimension} demands in DEMAND_SECTION, found {len(demands_map)}"
        )
    if not depot_ids:
        raise ValueError(f"Missing depot ID in DEPOT_SECTION of {file_path}")

    sorted_ids = sorted(coords_map.keys())
    id_to_idx = {node_id: idx for idx, node_id in enumerate(sorted_ids)}

    if depot_ids[0] not in id_to_idx:
        raise ValueError(f"Depot ID {depot_ids[0]} not found in node coordinates")
    depot_idx = id_to_idx[depot_ids[0]]

    coords = np.array([coords_map[nid] for nid in sorted_ids], dtype=np.float64)
    demands = np.array([demands_map[nid] for nid in sorted_ids], dtype=np.int64)

    diff = coords[:, None, :] - coords[None, :, :]
    dist = np.hypot(diff[:, :, 0], diff[:, :, 1])
    if round_distances:
        dist = np.floor(dist + 0.5)
    np.fill_diagonal(dist, 0.0)

    return CVRPInstance(
        name=name,
        distance_matrix=dist,
        demands=demands,
        capacity=capacity,
        depot=depot_idx,
        coords=coords,
        optimal_value=optimal_value,
        node_names=[str(nid) for nid in sorted_ids],
    )
