"""Prepare the static Recife/PE UBS & USF CVRP dataset and OSRM road distance matrix.

Usage:
    uv run python scripts/prepare_recife_data.py
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import io
import json
import math
from pathlib import Path
import re
import statistics
from typing import Iterable
import unicodedata
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
MEDICAMENTOS_CSV_URL = (
    "https://dados.recife.pe.gov.br/dataset/8ae2b6b5-51b5-403a-9dea-973a8ed1aca4/"
    "resource/1b8142f9-d801-4b54-88ca-5a1df3bd6884/download/medicamentos-por-unidade-de-saude.csv"
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


def _fetch_csv_rows(url: str) -> list[dict[str, str]]:
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    text = resp.content.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text), delimiter=";"))


def load_stock_rows(stock_csv_path: str | Path | None = None) -> list[dict[str, str]]:
    """Load pharmacy stock CSV rows from a local file or Recife Open Data."""
    if stock_csv_path is not None:
        text = Path(stock_csv_path).read_text(encoding="utf-8-sig")
        return list(csv.DictReader(io.StringIO(text), delimiter=";"))
    return _fetch_csv_rows(MEDICAMENTOS_CSV_URL)


def _parse_float(val: str) -> float | None:
    try:
        f = float(val.strip().replace(",", "."))
        return f if math.isfinite(f) else None
    except (ValueError, AttributeError):
        return None


_US_CODE_RE = re.compile(r"\bUS\s*0*(\d+(?:\.\d+)?)\b", re.IGNORECASE)
_PREFIX_TOKEN_RE = re.compile(r"^(?:us\s+\d+(?:\s+\d+)?|ubs|usf|psf|cs)\b\s*")


def normalize_text(text: str, strip_prefix_tokens: bool = False) -> str:
    """Normalize text via NFKD accent stripping, case folding, and punctuation cleanup."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    ascii_only = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    cleaned = re.sub(r"[^a-z0-9]+", " ", ascii_only.lower()).strip()
    if strip_prefix_tokens:
        while True:
            updated = _PREFIX_TOKEN_RE.sub("", cleaned).strip()
            if updated == cleaned:
                break
            cleaned = updated
    return cleaned


def extract_us_code(text: str) -> str | None:
    """Extract canonical 'US <number>' code (preserving decimal sub-units like 'US 128.1')."""
    match = _US_CODE_RE.search(text or "")
    if not match:
        return None
    return f"US {match.group(1)}"


@dataclass(frozen=True)
class StockSummary:
    """Aggregated pharmacy stock summary for a single (unidade, bairro) entry."""

    unidade: str
    bairro: str
    raw_stockouts: int
    total_items: int
    data_carga: str


def parse_stock_records(rows: Iterable[dict[str, str]]) -> list[StockSummary]:
    """Aggregate pharmacy stock rows per (unidade, bairro) on each unit's latest data_carga."""
    grouped: dict[tuple[str, str], list[tuple[str, float]]] = {}
    checked_columns = False

    for row in rows:
        if not checked_columns:
            missing = {"unidade", "bairro", "quantidade"} - set(row.keys())
            if missing:
                raise ValueError(
                    f"Stock CSV missing required columns: {sorted(missing)}"
                )
            checked_columns = True

        unidade = (row.get("unidade") or "").strip()
        bairro = (row.get("bairro") or "").strip()
        qty = _parse_float(row.get("quantidade") or "")
        if not unidade or qty is None:
            continue

        data_carga = (row.get("data_carga") or "").strip()
        grouped.setdefault((unidade, bairro), []).append((data_carga, qty))

    summaries: list[StockSummary] = []
    for (unidade, bairro), entries in sorted(grouped.items()):
        latest_date = max(date for date, _ in entries)
        latest_entries = [(d, q) for d, q in entries if d == latest_date]
        raw_stockouts = sum(1 for _, q in latest_entries if q == 0.0)
        summaries.append(
            StockSummary(
                unidade=unidade,
                bairro=bairro,
                raw_stockouts=raw_stockouts,
                total_items=len(latest_entries),
                data_carga=latest_date,
            )
        )
    return summaries


@dataclass(frozen=True)
class NodeStockLink:
    """Result of linking a customer health unit node to pharmacy stock records."""

    raw_proxy: float
    raw_stockouts: int | None
    total_items: int | None
    demand_match_method: str
    imputed_stockouts: float | None = None
    data_carga: str | None = None


def _disambiguate_stock_candidates(
    node: dict, candidates: list[StockSummary]
) -> StockSummary:
    if len(candidates) == 1:
        return candidates[0]
    node_bairro = normalize_text(node.get("bairro", ""))
    node_tokens = set(
        normalize_text(node.get("name", ""), strip_prefix_tokens=True).split()
    )

    def sort_key(s: StockSummary) -> tuple[int, int, str]:
        bairro_match = int(
            bool(node_bairro) and normalize_text(s.bairro) == node_bairro
        )
        stock_tokens = set(
            normalize_text(s.unidade, strip_prefix_tokens=True).split()
        )
        overlap = len(node_tokens & stock_tokens)
        return (-bairro_match, -overlap, s.unidade)

    return min(candidates, key=sort_key)


def link_nodes_to_stock(
    nodes: list[dict], stock_summaries: list[StockSummary]
) -> dict[int, NodeStockLink]:
    """Link customer nodes to stock summaries via US code, normalized name+bairro, or median fallback.

    Returns a mapping from node index in ``nodes`` (excluding DEPOT nodes) to its ``NodeStockLink``.
    """
    by_us_code: dict[str, list[StockSummary]] = {}
    by_name_bairro: dict[tuple[str, str], list[StockSummary]] = {}

    for summary in stock_summaries:
        us_code = extract_us_code(summary.unidade)
        if us_code is not None:
            by_us_code.setdefault(us_code, []).append(summary)
        norm_name = normalize_text(summary.unidade, strip_prefix_tokens=True)
        norm_bairro = normalize_text(summary.bairro)
        if norm_name:
            by_name_bairro.setdefault((norm_name, norm_bairro), []).append(summary)

    links: dict[int, NodeStockLink] = {}
    matched_by_type: dict[str, list[int]] = {}
    all_matched: list[int] = []
    unmatched_indices: list[int] = []

    for idx, node in enumerate(nodes):
        if node.get("type") == "DEPOT":
            continue

        matched_summary: StockSummary | None = None
        method = ""

        us_code = extract_us_code(node.get("name", ""))
        if us_code is not None and us_code in by_us_code:
            matched_summary = _disambiguate_stock_candidates(node, by_us_code[us_code])
            method = "us_code"
        else:
            key = (
                normalize_text(node.get("name", ""), strip_prefix_tokens=True),
                normalize_text(node.get("bairro", "")),
            )
            if key[0] and key in by_name_bairro:
                matched_summary = min(by_name_bairro[key], key=lambda s: s.unidade)
                method = "name_bairro"

        if matched_summary is not None:
            links[idx] = NodeStockLink(
                raw_proxy=float(matched_summary.raw_stockouts),
                raw_stockouts=matched_summary.raw_stockouts,
                total_items=matched_summary.total_items,
                demand_match_method=method,
                data_carga=matched_summary.data_carga or None,
            )
            matched_by_type.setdefault(node.get("type", ""), []).append(
                matched_summary.raw_stockouts
            )
            all_matched.append(matched_summary.raw_stockouts)
        else:
            unmatched_indices.append(idx)

    if unmatched_indices and not all_matched:
        raise ValueError(
            "Zero customer health units matched any pharmacy stock record."
        )

    for idx in unmatched_indices:
        node = nodes[idx]
        unit_type = node.get("type", "")
        type_values = matched_by_type.get(unit_type)
        if type_values:
            imputed = float(statistics.median(type_values))
            method = "type_median_fallback"
        else:
            imputed = float(statistics.median(all_matched))
            method = "global_median_fallback"

        links[idx] = NodeStockLink(
            raw_proxy=imputed,
            raw_stockouts=None,
            total_items=None,
            demand_match_method=method,
            imputed_stockouts=imputed,
        )

    return links


def validate_scaling_bounds(d_min: int, d_max: int, capacity: int) -> None:
    """Validate that CVRP demand scaling bounds satisfy 1 <= d_min <= d_max <= capacity."""
    if not (1 <= d_min <= d_max <= capacity):
        raise ValueError(
            f"Invalid demand scaling bounds: require 1 <= d_min <= d_max <= capacity, "
            f"got d_min={d_min}, d_max={d_max}, capacity={capacity}."
        )


def scale_demands_minmax(
    raw_values: list[float],
    d_min: int = 10,
    d_max: int = 40,
    capacity: int = 100,
) -> list[int]:
    """Scale raw stockout proxies into bounded integer CVRP demands [d_min, d_max]."""
    validate_scaling_bounds(d_min, d_max, capacity)
    if not raw_values:
        return []

    min_x = min(raw_values)
    max_x = max(raw_values)
    if max_x == min_x:
        constant = int(round((d_min + d_max) / 2))
        return [constant for _ in raw_values]

    span = max_x - min_x
    scaled_demands: list[int] = []
    for x in raw_values:
        scaled = d_min + ((x - min_x) / span) * (d_max - d_min)
        clamped = max(d_min, min(d_max, int(round(scaled))))
        scaled_demands.append(clamped)
    return scaled_demands


def assign_empirical_demands(
    nodes: list[dict],
    stock_summaries: list[StockSummary],
    d_min: int = 10,
    d_max: int = 40,
    capacity: int = 100,
) -> dict:
    """Assign empirical stockout-based demands and provenance metadata to nodes in place."""
    validate_scaling_bounds(d_min, d_max, capacity)
    links = link_nodes_to_stock(nodes, stock_summaries)

    customer_indices = [idx for idx, n in enumerate(nodes) if n.get("type") != "DEPOT"]
    raw_proxies = [links[idx].raw_proxy for idx in customer_indices]
    scaled = scale_demands_minmax(
        raw_proxies, d_min=d_min, d_max=d_max, capacity=capacity
    )

    scaled_iter = iter(scaled)
    for idx, node in enumerate(nodes):
        if node.get("type") == "DEPOT":
            node["demand"] = 0
            continue
        link = links[idx]
        node["demand"] = next(scaled_iter)
        node["raw_stockouts"] = link.raw_stockouts
        node["total_items"] = link.total_items
        node["demand_match_method"] = link.demand_match_method
        if link.imputed_stockouts is not None:
            node["imputed_stockouts"] = link.imputed_stockouts
        else:
            node.pop("imputed_stockouts", None)

    dates = sorted({link.data_carga for link in links.values() if link.data_carga})
    if len(dates) == 1:
        data_carga_val: str | list[str] | None = dates[0]
    elif dates:
        data_carga_val = dates
    else:
        data_carga_val = None

    observed_raw = [
        link.raw_stockouts
        for link in links.values()
        if link.raw_stockouts is not None
    ]
    raw_min = min(observed_raw) if observed_raw else min(raw_proxies)
    raw_max = max(observed_raw) if observed_raw else max(raw_proxies)

    match_methods = (
        "us_code",
        "name_bairro",
        "type_median_fallback",
        "global_median_fallback",
    )
    match_summary = {
        method: sum(
            1 for link in links.values() if link.demand_match_method == method
        )
        for method in match_methods
    }

    return {
        "method": "stockout_count_minmax",
        "source_url": MEDICAMENTOS_CSV_URL,
        "data_carga": data_carga_val,
        "d_min": d_min,
        "d_max": d_max,
        "raw_min": raw_min,
        "raw_max": raw_max,
        "match_summary": match_summary,
    }


def _is_placeholder_cnes(cnes: str) -> bool:
    """Return True when CNES is empty or consists solely of placeholder digits ('0' or '9')."""
    cleaned = (cnes or "").strip()
    return not cleaned or all(ch in {"0", "9"} for ch in cleaned)


def select_recife_nodes(
    ubs_rows: Iterable[dict[str, str]],
    usf_rows: Iterable[dict[str, str]],
    target_customers: int = 40,
) -> list[dict]:
    """Select and deduplicate Recife UBS/USF customer nodes up to target_customers."""
    seen_us_codes: set[str] = set()
    seen_cnes: set[str] = set()
    seen_name_bairro: set[tuple[str, str]] = set()
    seen_coords: set[tuple[float, float]] = set()
    seen_ids: set[str] = {str(DEPOT_NODE["id"])}
    selected: list[dict] = []

    def try_add(row: dict[str, str], unit_type: str) -> bool:
        lat = _parse_float(row.get("latitude", ""))
        lon = _parse_float(row.get("longitude", ""))
        if lat is None or lon is None:
            return False
        if not (-8.20 <= lat <= -7.90 and -35.05 <= lon <= -34.80):
            return False

        name = (row.get("nome_oficial") or "").strip()
        bairro = (row.get("bairro") or "").strip()
        cnes = (row.get("cnes") or "").strip()
        us_code = extract_us_code(name)
        coord_key = (round(lat, 5), round(lon, 5))
        norm_name = normalize_text(name, strip_prefix_tokens=True)
        norm_bairro = normalize_text(bairro)
        name_bairro_key = (norm_name, norm_bairro) if norm_name else None

        if us_code is not None and us_code in seen_us_codes:
            return False
        if not _is_placeholder_cnes(cnes) and cnes in seen_cnes:
            return False
        if name_bairro_key is not None and name_bairro_key in seen_name_bairro:
            return False
        if coord_key in seen_coords:
            return False

        if not _is_placeholder_cnes(cnes):
            base_id = f"{unit_type}-{cnes}"
        elif us_code is not None:
            base_id = f"{unit_type}-US{us_code.split()[1]}"
        else:
            base_id = f"{unit_type}-{len(selected) + 1:04d}"

        node_id = base_id
        suffix = 2
        while node_id in seen_ids:
            node_id = f"{base_id}-{suffix}"
            suffix += 1

        seen_coords.add(coord_key)
        seen_ids.add(node_id)
        if us_code is not None:
            seen_us_codes.add(us_code)
        if not _is_placeholder_cnes(cnes):
            seen_cnes.add(cnes)
        if name_bairro_key is not None:
            seen_name_bairro.add(name_bairro_key)

        selected.append(
            {
                "id": node_id,
                "name": name or f"{unit_type} {cnes or len(selected) + 1}",
                "type": unit_type,
                "rpa": (row.get("rpa") or "").strip(),
                "bairro": bairro,
                "lat": lat,
                "lon": lon,
                "demand": 0,
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

    nodes = [dict(DEPOT_NODE)] + selected
    node_ids = [n["id"] for n in nodes]
    if len(node_ids) != len(set(node_ids)):
        raise ValueError("Duplicate node IDs generated during node selection.")
    us_codes = [
        code
        for n in selected
        if (code := extract_us_code(n.get("name", ""))) is not None
    ]
    if len(us_codes) != len(set(us_codes)):
        raise ValueError("Duplicate canonical US codes selected during node selection.")
    if len(selected) != target_customers:
        raise ValueError(
            f"Expected {target_customers} unique customer health units, got {len(selected)}."
        )
    return nodes


def _collect_recife_nodes(target_customers: int = 40) -> list[dict]:
    ubs_rows = _fetch_csv_rows(UBS_CSV_URL)
    usf_rows = _fetch_csv_rows(USF_CSV_URL)
    return select_recife_nodes(ubs_rows, usf_rows, target_customers=target_customers)


def _fetch_osrm_matrix(latlon: np.ndarray) -> np.ndarray:
    """Fetch complete pairwise OSRM driving distances in km; fail fast on errors."""
    coords_str = ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in latlon)
    url = OSRM_TABLE_URL.format(coords=coords_str)
    try:
        resp = requests.get(url, params={"annotations": "distance"}, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
    except Exception as exc:
        raise RuntimeError(f"OSRM road matrix request failed: {exc}") from exc

    if payload.get("code") != "Ok" or "distances" not in payload:
        raise RuntimeError(
            f"OSRM returned invalid table response: code={payload.get('code')!r}"
        )

    raw = payload["distances"]
    n = len(latlon)
    mat = np.empty((n, n), dtype=np.float64)
    for i in range(n):
        for j in range(n):
            val = raw[i][j]
            if val is None:
                raise RuntimeError(
                    f"OSRM returned unreachable (None) distance at ({i}, {j})"
                )
            mat[i, j] = float(val) / 1000.0
    np.fill_diagonal(mat, 0.0)
    return mat


def main(
    output_dir: str | Path = "data/recife_ubs",
    *,
    d_min: int = 10,
    d_max: int = 40,
    capacity: int = 100,
    stock_csv_path: str | Path | None = None,
) -> None:
    validate_scaling_bounds(d_min, d_max, capacity)

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    nodes = _collect_recife_nodes(target_customers=40)
    stock_rows = load_stock_rows(stock_csv_path)
    stock_summaries = parse_stock_records(stock_rows)
    demand_metadata = assign_empirical_demands(
        nodes,
        stock_summaries,
        d_min=d_min,
        d_max=d_max,
        capacity=capacity,
    )

    latlon = np.array([[n["lat"], n["lon"]] for n in nodes], dtype=np.float64)

    road_matrix = _fetch_osrm_matrix(latlon)
    source_note = (
        "Recife Open Data (UBS/USF + medicamentos-por-unidade-de-saude.csv) "
        "+ OSRM driving table (km)"
    )

    metadata = {
        "name": "Recife-UBS-40",
        "capacity": capacity,
        "depot": 0,
        "distance_unit": "km",
        "source": source_note,
        "demand_metadata": demand_metadata,
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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare the static Recife/PE UBS & USF CVRP dataset with "
            "pharmacy stockout replenishment demands."
        )
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/recife_ubs"),
        help="Output directory for recife_ubs.json and distance_matrix_road.npy.",
    )
    parser.add_argument(
        "--d-min",
        type=int,
        default=10,
        help="Minimum scaled customer demand (default: 10).",
    )
    parser.add_argument(
        "--d-max",
        type=int,
        default=40,
        help="Maximum scaled customer demand (default: 40).",
    )
    parser.add_argument(
        "--capacity",
        type=int,
        default=100,
        help="Vehicle capacity (default: 100).",
    )
    parser.add_argument(
        "--stock-csv",
        type=Path,
        default=None,
        help="Optional local path to medicamentos-por-unidade-de-saude.csv.",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = parse_args()
    main(
        output_dir=args.output_dir,
        d_min=args.d_min,
        d_max=args.d_max,
        capacity=args.capacity,
        stock_csv_path=args.stock_csv,
    )
