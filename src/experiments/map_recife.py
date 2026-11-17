"""Interactive Folium map visualization for Recife/PE CVRP routes."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence
import folium
import numpy as np

from src.data.models import CVRPInstance

_PALETTE = [
    "#e6194b",
    "#3cb44b",
    "#4363d8",
    "#f58231",
    "#911eb4",
    "#46f0f0",
    "#f032e6",
    "#bcf60c",
    "#fabebe",
    "#008080",
    "#e6beff",
    "#9a6324",
]


def generate_recife_map(
    instance: CVRPInstance,
    routes: Sequence[Sequence[int]],
    output_path: str | Path = "results/recife_map.html",
) -> Path:
    """Render an interactive Folium HTML map with depot, health units, and vehicle routes."""
    if instance.latlon is None:
        raise ValueError("Instance must have latlon coordinates to generate a Folium map")

    latlon = instance.latlon
    depot = instance.depot
    depot_lat, depot_lon = float(latlon[depot, 0]), float(latlon[depot, 1])

    center_lat = float(np.mean(latlon[:, 0]))
    center_lon = float(np.mean(latlon[:, 1]))
    fmap = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles="OpenStreetMap")

    depot_name = (
        instance.node_names[depot] if instance.node_names else f"Depot ({depot})"
    )
    folium.Marker(
        location=[depot_lat, depot_lon],
        popup=f"<b>{depot_name}</b><br>Central Depot",
        tooltip=depot_name,
        icon=folium.Icon(color="black", icon="home", prefix="fa"),
    ).add_to(fmap)

    for v_idx, route in enumerate(routes):
        color = _PALETTE[v_idx % len(_PALETTE)]
        path_coords = [[depot_lat, depot_lon]]
        for node in route:
            lat, lon = float(latlon[node, 0]), float(latlon[node, 1])
            path_coords.append([lat, lon])
            node_name = (
                instance.node_names[node] if instance.node_names else f"Unit {node}"
            )
            demand = int(instance.demands[node])
            folium.CircleMarker(
                location=[lat, lon],
                radius=6,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.85,
                popup=(
                    f"<b>{node_name}</b><br>"
                    f"Vehicle: {v_idx + 1}<br>"
                    f"Demand: {demand}"
                ),
                tooltip=f"V{v_idx + 1}: {node_name}",
            ).add_to(fmap)
        path_coords.append([depot_lat, depot_lon])

        route_load = int(sum(instance.demands[n] for n in route))
        folium.PolyLine(
            locations=path_coords,
            color=color,
            weight=3.5,
            opacity=0.8,
            tooltip=f"Vehicle {v_idx + 1} ({len(route)} units, load {route_load}/{instance.capacity})",
        ).add_to(fmap)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fmap.save(str(out))
    return out
