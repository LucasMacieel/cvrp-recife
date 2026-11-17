"""Prepare the static Recife/PE UBS & USF CVRP dataset and OSRM road distance matrix.

Usage:
    python scripts/prepare_recife_data.py
"""

from __future__ import annotations

import csv
import io
import json
import math
from pathlib import Path
import numpy as np
import requests

UBS_CSV_URL = (
    "https://dados.recife.pe.gov.br/dataset/c63f29cf-682c-4593-9f31-40dd8bd8204f/"
    "resource/7927e663-6753-489c-943c-f20cdd72555e/download/unidades-basicas-de-saude-ubs.csv"
)
USF_CSV_URL = (
    "https://dados.recife.pe.gov.br/dataset/af30af9d-52e3-4f62-bd3b-dd3764958952/"
    "resource/64cc8ab3-bd69-4629-b145-74552fe31e1c/download/unidades-de-saude-da-familia-usf.csv"
)
OSRM_TABLE_URL = "https://router.project-osrm.org/table/v1/driving/{coords}"

DEPOT_NODE = {
    "id": "DEPOT-CAF",
    "name": "Central de Abastecimento Farmacêutico (CAF Recife)",
    "type": "DEPOT",
    "rpa": "5",
    "bairro": "Bongi",
    "lat": -8.0598,
    "lon": -34.9225,
    "demand": 0,
}


def haversine_km(latlon: np.ndarray) -> np.ndarray:
    """Compute pairwise Haversine distances in kilometers for (N, 2) lat/lon."""
    rad = np.radians(latlon)
    lat = rad[:, 0:1]
    lon = rad[:, 1:2]
    dlat = lat - lat.T
    dlon = lon - lon.T
    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat) * np.cos(lat.T) * np.sin(dlon / 2.0) ** 2
    c = 2.0 * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))
    dist = 6371.0088 * c
    np.fill_diagonal(dist, 0.0)
    return dist


def _fetch_csv_rows(url: str) -> list[dict[str, str]]:
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    return list(csv.DictReader(io.StringIO(resp.text), delimiter=";"))


def _parse_float(val: str) -> float | None:
    try:
        f = float(val.strip().replace(",", "."))
        return f if math.isfinite(f) else None
    except (ValueError, AttributeError):
        return None


def _collect_recife_nodes(target_customers: int = 40, seed: int = 42) -> list[dict]:
    rng = np.random.default_rng(seed)
    ubs_rows = _fetch_csv_rows(UBS_CSV_URL)
    usf_rows = _fetch_csv_rows(USF_CSV_URL)

    seen_coords: set[tuple[float, float]] = set()
    selected: list[dict] = []

    def try_add(row: dict[str, str], unit_type: str) -> bool:
        lat = _parse_float(row.get("latitude", ""))
        lon = _parse_float(row.get("longitude", ""))
        if lat is None or lon is None:
            return False
        if not (-8.20 <= lat <= -7.90 and -35.05 <= lon <= -34.80):
            return False
        key = (round(lat, 5), round(lon, 5))
        if key in seen_coords:
            return False
        seen_coords.add(key)
        cnes = (row.get("cnes") or f"{len(selected):04d}").strip()
        selected.append(
            {
                "id": f"{unit_type}-{cnes}",
                "name": row.get("nome_oficial", "").strip() or f"{unit_type} {cnes}",
                "type": unit_type,
                "rpa": (row.get("rpa") or "").strip(),
                "bairro": (row.get("bairro") or "").strip(),
                "lat": lat,
                "lon": lon,
                "demand": int(rng.integers(10, 31)),
            }
        )
        return True

    for row in ubs_rows:
        if len(selected) >= target_customers:
            break
        try_add(row, "UBS")

    # Round-robin across RPAs from USFs to cover all regions of Recife
    by_rpa: dict[str, list[dict[str, str]]] = {}
    for row in usf_rows:
        rpa = (row.get("rpa") or "0").strip()
        by_rpa.setdefault(rpa, []).append(row)

    rpa_keys = sorted(by_rpa.keys())
    idx = 0
    while len(selected) < target_customers and any(by_rpa.values()):
        progressed = False
        for rpa in rpa_keys:
            if len(selected) >= target_customers:
                break
            bucket = by_rpa[rpa]
            while bucket:
                candidate = bucket.pop(0)
                if try_add(candidate, "USF"):
                    progressed = True
                    break
        if not progressed:
            break
        idx += 1

    return [DEPOT_NODE] + selected


def _fetch_osrm_matrix(latlon: np.ndarray) -> np.ndarray | None:
    coords_str = ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in latlon)
    url = OSRM_TABLE_URL.format(coords=coords_str)
    try:
        resp = requests.get(url, params={"annotations": "distance"}, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("code") != "Ok" or "distances" not in payload:
            return None
        raw = payload["distances"]
        n = len(latlon)
        fallback = haversine_km(latlon)
        mat = np.empty((n, n), dtype=np.float64)
        for i in range(n):
            for j in range(n):
                val = raw[i][j]
                mat[i, j] = fallback[i, j] if val is None else float(val) / 1000.0
        np.fill_diagonal(mat, 0.0)
        return mat
    except Exception as exc:
        print(f"Warning: OSRM request failed ({exc}); falling back to Haversine.")
        return None


def main(output_dir: str | Path = "data/recife_ubs") -> None:
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    nodes = _collect_recife_nodes(target_customers=40, seed=42)
    latlon = np.array([[n["lat"], n["lon"]] for n in nodes], dtype=np.float64)

    road_matrix = _fetch_osrm_matrix(latlon)
    source_note = "Recife Open Data (UBS/USF) + OSRM driving table (km)"
    if road_matrix is None:
        road_matrix = haversine_km(latlon)
        source_note = "Recife Open Data (UBS/USF) + Haversine fallback (km)"

    metadata = {
        "name": "Recife-UBS-40",
        "capacity": 100,
        "depot": 0,
        "distance_unit": "km",
        "source": source_note,
        "nodes": nodes,
    }

    (out_path / "recife_ubs.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    np.save(out_path / "distance_matrix_road.npy", road_matrix)
    print(
        f"Saved {len(nodes)} nodes (1 depot + {len(nodes) - 1} units) and "
        f"{road_matrix.shape} matrix to {out_path}"
    )


if __name__ == "__main__":
    main()
