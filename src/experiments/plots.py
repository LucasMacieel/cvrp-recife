"""Analytical plots (convergence curves, comparative boxplots, and best-solution routes) for CVRP."""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from collections.abc import Iterable, Sequence
from io import BytesIO
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import requests
from PIL import Image

from src.data.models import CVRPInstance
from src.experiments.map_recife import _fetch_osrm_route_geometry

logger = logging.getLogger(__name__)

_MERCATOR_R = 6378137.0
_MAX_MERCATOR_LAT = 85.0511287798066
_WORLD_HALF = math.pi * _MERCATOR_R
_TILE_SIZE = 256
_OSM_TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
_OSM_USER_AGENT = "cvrp-recife/1.0 (+https://github.com/lucasmacieel/cvrp-recife)"


def _latlon_to_mercator(lat: float, lon: float) -> tuple[float, float]:
    """Convert geographic (lat, lon) degrees to Web Mercator (EPSG:3857) meters."""
    clamped_lat = max(-_MAX_MERCATOR_LAT, min(_MAX_MERCATOR_LAT, float(lat)))
    x = _MERCATOR_R * math.radians(float(lon))
    y = _MERCATOR_R * math.log(
        math.tan(math.pi / 4.0 + math.radians(clamped_lat) / 2.0)
    )
    return x, y


def _mercator_to_latlon(x: float, y: float) -> tuple[float, float]:
    """Convert Web Mercator (EPSG:3857) meters to geographic (lat, lon) degrees."""
    lon = math.degrees(float(x) / _MERCATOR_R)
    lat = math.degrees(
        2.0 * math.atan(math.exp(float(y) / _MERCATOR_R)) - math.pi / 2.0
    )
    return lat, lon


def _latlon_to_tile_xy(lat: float, lon: float, zoom: int) -> tuple[int, int]:
    """Convert (lat, lon) degrees to Slippy Map tile indices (x, y) at zoom."""
    clamped_lat = max(-_MAX_MERCATOR_LAT, min(_MAX_MERCATOR_LAT, float(lat)))
    n = 2**zoom
    tx = int((float(lon) + 180.0) / 360.0 * n)
    lat_rad = math.radians(clamped_lat)
    ty = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return max(0, min(n - 1, tx)), max(0, min(n - 1, ty))


def _tile_xy_to_mercator_bounds(
    tx: int, ty: int, zoom: int
) -> tuple[float, float, float, float]:
    """Return Web Mercator (mx_min, mx_max, my_min, my_max) bounds for a tile."""
    n = 2**zoom
    tile_span = (2.0 * _WORLD_HALF) / n
    mx_min = -_WORLD_HALF + tx * tile_span
    mx_max = mx_min + tile_span
    my_max = _WORLD_HALF - ty * tile_span
    my_min = my_max - tile_span
    return mx_min, mx_max, my_min, my_max


def _compute_padded_mercator_bounds(
    lats: Iterable[float],
    lons: Iterable[float],
    pad_frac: float = 0.12,
    min_span_m: float = 1000.0,
    min_aspect: float = 1.15,
) -> tuple[float, float, float, float]:
    """Compute padded Web Mercator bounding box (mx_min, mx_max, my_min, my_max)."""
    pts = [_latlon_to_mercator(lat, lon) for lat, lon in zip(lats, lons, strict=True)]
    mxs = [p[0] for p in pts]
    mys = [p[1] for p in pts]
    mx_min, mx_max = min(mxs), max(mxs)
    my_min, my_max = min(mys), max(mys)

    if mx_max - mx_min < min_span_m:
        mid_x = 0.5 * (mx_min + mx_max)
        mx_min, mx_max = mid_x - 0.5 * min_span_m, mid_x + 0.5 * min_span_m
    if my_max - my_min < min_span_m:
        mid_y = 0.5 * (my_min + my_max)
        my_min, my_max = mid_y - 0.5 * min_span_m, mid_y + 0.5 * min_span_m

    pad_x = (mx_max - mx_min) * pad_frac
    pad_y = (my_max - my_min) * pad_frac
    mx_min, mx_max = mx_min - pad_x, mx_max + pad_x
    my_min, my_max = my_min - pad_y, my_max + pad_y

    span_x = mx_max - mx_min
    span_y = my_max - my_min
    if span_x < min_aspect * span_y:
        target_x = min_aspect * span_y
        mid_x = 0.5 * (mx_min + mx_max)
        mx_min, mx_max = mid_x - 0.5 * target_x, mid_x + 0.5 * target_x

    return mx_min, mx_max, my_min, my_max


def _select_osm_zoom(
    mx_min: float,
    mx_max: float,
    my_min: float,
    my_max: float,
    max_tiles: int = 25,
    min_zoom: int = 1,
    max_zoom: int = 15,
) -> tuple[int, int, int, int, int]:
    """Select the highest OSM zoom level whose covering grid uses <= max_tiles."""
    lat_min, lon_min = _mercator_to_latlon(mx_min, my_min)
    lat_max, lon_max = _mercator_to_latlon(mx_max, my_max)

    for z in range(max_zoom, min_zoom - 1, -1):
        x0, y1 = _latlon_to_tile_xy(lat_min, lon_min, z)
        x1, y0 = _latlon_to_tile_xy(lat_max, lon_max, z)
        if (x1 - x0 + 1) * (y1 - y0 + 1) <= max_tiles:
            return z, x0, x1, y0, y1

    x0, y1 = _latlon_to_tile_xy(lat_min, lon_min, min_zoom)
    x1, y0 = _latlon_to_tile_xy(lat_max, lon_max, min_zoom)
    return min_zoom, x0, x1, y0, y1


def _fetch_osm_basemap(
    mx_min: float,
    mx_max: float,
    my_min: float,
    my_max: float,
    timeout: float = 5.0,
) -> tuple[Image.Image, tuple[float, float, float, float]] | None:
    """Fetch and stitch OSM raster tiles for the given Web Mercator bounds."""
    z, x0, x1, y0, y1 = _select_osm_zoom(mx_min, mx_max, my_min, my_max)
    width = (x1 - x0 + 1) * _TILE_SIZE
    height = (y1 - y0 + 1) * _TILE_SIZE
    canvas = Image.new("RGB", (width, height))

    try:
        with requests.Session() as session:
            session.headers.update({"User-Agent": _OSM_USER_AGENT})
            for tx in range(x0, x1 + 1):
                for ty in range(y0, y1 + 1):
                    url = _OSM_TILE_URL.format(z=z, x=tx, y=ty)
                    resp = session.get(url, timeout=timeout)
                    resp.raise_for_status()
                    with Image.open(BytesIO(resp.content)) as tile_img:
                        canvas.paste(
                            tile_img.convert("RGB"),
                            ((tx - x0) * _TILE_SIZE, (ty - y0) * _TILE_SIZE),
                        )
    except (requests.RequestException, OSError, ValueError) as exc:
        logger.warning(
            "OSM basemap tile fetch failed (%s); falling back to plain coordinate plot.",
            exc,
        )
        return None

    ext_mx_min, _, _, ext_my_max = _tile_xy_to_mercator_bounds(x0, y0, z)
    _, ext_mx_max, ext_my_min, _ = _tile_xy_to_mercator_bounds(x1, y1, z)
    return canvas, (ext_mx_min, ext_mx_max, ext_my_min, ext_my_max)


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
    use_basemap: bool = True,
) -> Path:
    """Plot a static Matplotlib visualization of CVRP routes (road-snapped + OSM basemap when latlon)."""
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

    route_polylines: list[list[list[float]]] = []
    if is_geo:
        for route in routes:
            waypoints = [[depot_y, depot_x]]
            for node in route:
                waypoints.append([float(ys_all[node]), float(xs_all[node])])
            waypoints.append([depot_y, depot_x])

            poly = waypoints
            if use_osrm and route:
                road_coords = _fetch_osrm_route_geometry(waypoints)
                if road_coords is not None:
                    poly = road_coords
            route_polylines.append(poly)

    basemap: tuple[Image.Image, tuple[float, float, float, float]] | None = None
    mercator_bounds: tuple[float, float, float, float] | None = None
    if is_geo and use_basemap:
        all_lats = [float(v) for v in ys_all]
        all_lons = [float(v) for v in xs_all]
        for poly in route_polylines:
            for pt_lat, pt_lon in poly:
                all_lats.append(float(pt_lat))
                all_lons.append(float(pt_lon))
        mercator_bounds = _compute_padded_mercator_bounds(all_lats, all_lons)
        basemap = _fetch_osm_basemap(*mercator_bounds)

    has_basemap = is_geo and basemap is not None and mercator_bounds is not None

    def _to_plot_xy(x_val: float, y_val: float) -> tuple[float, float]:
        if has_basemap:
            return _latlon_to_mercator(y_val, x_val)
        return x_val, y_val

    fig, ax = plt.subplots(figsize=(7.5, 6.2))
    cmap = plt.get_cmap("tab10")

    if has_basemap:
        assert basemap is not None
        basemap_img, extent = basemap
        ax.imshow(basemap_img, extent=extent, origin="upper", alpha=0.90, zorder=1)

    line_width = 2.4 if has_basemap else 1.8
    line_alpha = 0.92 if has_basemap else 0.9

    for v_idx, route in enumerate(routes):
        color = cmap(v_idx % 10)
        if is_geo:
            poly = route_polylines[v_idx]
            transformed = [_to_plot_xy(float(pt[1]), float(pt[0])) for pt in poly]
        else:
            node_seq = [depot, *route, depot]
            transformed = [(float(xs_all[n]), float(ys_all[n])) for n in node_seq]
        line_xs = [pt[0] for pt in transformed]
        line_ys = [pt[1] for pt in transformed]

        ax.plot(
            line_xs,
            line_ys,
            color=color,
            linewidth=line_width,
            alpha=line_alpha,
            label=f"Route {v_idx + 1} ({len(route)} units)",
            zorder=3,
        )
        if route:
            cust_pts = [_to_plot_xy(float(xs_all[n]), float(ys_all[n])) for n in route]
            ax.scatter(
                [pt[0] for pt in cust_pts],
                [pt[1] for pt in cust_pts],
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

    plot_depot_x, plot_depot_y = _to_plot_xy(depot_x, depot_y)
    ax.scatter(
        [plot_depot_x],
        [plot_depot_y],
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
    else:
        title = (
            f"Best {method_label} Solution — {instance.name} "
            f"({distance:.1f}, {len(routes)} routes)"
        )

    ax.set_title(title, fontweight="bold")
    if has_basemap:
        assert mercator_bounds is not None
        mx_min, mx_max, my_min, my_max = mercator_bounds
        ax.set_xlim(mx_min, mx_max)
        ax.set_ylim(my_min, my_max)
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        ax.text(
            0.99,
            0.01,
            "© OpenStreetMap contributors",
            transform=ax.transAxes,
            ha="right",
            va="bottom",
            fontsize=7,
            color="#333333",
            bbox={
                "facecolor": "white",
                "alpha": 0.75,
                "edgecolor": "none",
                "pad": 1.5,
            },
            zorder=7,
        )
        legend_anchor = (0.5, -0.03)
    else:
        if is_geo:
            ax.set_xlabel("Longitude (°)")
            ax.set_ylabel("Latitude (°)")
        else:
            ax.set_xlabel("X")
            ax.set_ylabel("Y")
        ax.set_aspect("equal", adjustable="datalim")
        ax.grid(True, linestyle="--", alpha=0.4)
        legend_anchor = (0.5, -0.12)

    ax.legend(
        loc="upper center",
        bbox_to_anchor=legend_anchor,
        ncol=3,
        frameon=True,
    )

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return out
