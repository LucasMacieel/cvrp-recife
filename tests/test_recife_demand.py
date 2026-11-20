"""Unit tests for Recife data-driven pharmacy stockout demand estimation."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import requests

from scripts.prepare_recife_data import (
    StockSummary,
    _fetch_osrm_matrix,
    assign_empirical_demands,
    extract_us_code,
    link_nodes_to_stock,
    load_stock_rows,
    normalize_text,
    parse_stock_records,
    scale_demands_minmax,
    select_recife_nodes,
)


def test_extract_us_code_handles_decimals_and_leading_zeros() -> None:
    assert extract_us_code("US 128 Policlínica Lessa de Andrade") == "US 128"
    assert extract_us_code("US 128.1 Anexo") == "US 128.1"
    assert extract_us_code("us0045 CS Teste") == "US 45"
    assert extract_us_code("UBS Sem Codigo") is None
    assert extract_us_code("US 128") != extract_us_code("US 128.1")


def test_normalize_text_strips_accents_and_optional_prefixes() -> None:
    assert normalize_text("São José - Córrego do Jenipapo!") == "sao jose corrego do jenipapo"
    assert (
        normalize_text("US 123 CS Prof César Montezuma", strip_prefix_tokens=True)
        == "prof cesar montezuma"
    )
    assert (
        normalize_text("USF Alto do Maracanã", strip_prefix_tokens=True)
        == "alto do maracana"
    )


def test_parse_stock_records_comma_decimal_and_snapshot_filtering() -> None:
    rows = [
        # Older snapshot should be ignored for US 103
        {
            "unidade": "US 103 CS Prof Mário Ramos",
            "bairro": "CASA AMARELA",
            "quantidade": "0,0",
            "data_carga": "2024-09-01",
        },
        # Latest snapshot for US 103: 3 zero items ("0,0", "0.0", "0"), 1 non-zero, 1 invalid
        {
            "unidade": "US 103 CS Prof Mário Ramos",
            "bairro": "CASA AMARELA",
            "quantidade": "0,0",
            "data_carga": "2024-10-10",
        },
        {
            "unidade": "US 103 CS Prof Mário Ramos",
            "bairro": "CASA AMARELA",
            "quantidade": "0.0",
            "data_carga": "2024-10-10",
        },
        {
            "unidade": "US 103 CS Prof Mário Ramos",
            "bairro": "CASA AMARELA",
            "quantidade": "0",
            "data_carga": "2024-10-10",
        },
        {
            "unidade": "US 103 CS Prof Mário Ramos",
            "bairro": "CASA AMARELA",
            "quantidade": "76,0",
            "data_carga": "2024-10-10",
        },
        {
            "unidade": "US 103 CS Prof Mário Ramos",
            "bairro": "CASA AMARELA",
            "quantidade": "N/A",
            "data_carga": "2024-10-10",
        },
    ]

    summaries = parse_stock_records(rows)
    assert len(summaries) == 1
    s = summaries[0]
    assert s.raw_stockouts == 3
    assert s.total_items == 4
    assert s.data_carga == "2024-10-10"


def test_load_stock_rows_utf8_sig_local_csv(tmp_path: Path) -> None:
    csv_path = tmp_path / "stock.csv"
    content = (
        "\ufeffunidade;bairro;quantidade;data_carga\n"
        "US 123 CS Montezuma;BAIRRO DO RECIFE;0,0;2024-10-10\n"
        "US 123 CS Montezuma;BAIRRO DO RECIFE;12,5;2024-10-10\n"
    )
    csv_path.write_text(content, encoding="utf-8")

    rows = load_stock_rows(csv_path)
    summaries = parse_stock_records(rows)
    assert len(summaries) == 1
    assert summaries[0].raw_stockouts == 1
    assert summaries[0].total_items == 2


def test_parse_stock_records_missing_columns_raises() -> None:
    with pytest.raises(ValueError, match="missing required columns"):
        parse_stock_records([{"unidade": "US 1", "bairro": "Centro"}])


def test_link_nodes_to_stock_all_tiers_and_disambiguation() -> None:
    nodes = [
        {"id": "DEPOT-CAF", "name": "CAF", "type": "DEPOT", "bairro": "Bongi"},
        # Tier 1: US code with disambiguation (two entries share US 121)
        {
            "id": "UBS-1",
            "name": "US 121 CS Joaquim Cavalcanti",
            "type": "UBS",
            "bairro": "TORROES",
        },
        # Tier 1: second UBS for median calculation
        {
            "id": "UBS-2",
            "name": "US 103 CS Mário Ramos",
            "type": "UBS",
            "bairro": "CASA AMARELA",
        },
        # Tier 2: no US code in stock, matches by normalized (name, bairro)
        {
            "id": "UBS-3",
            "name": "US 999 USF São José",
            "type": "UBS",
            "bairro": "SÃO JOSÉ",
        },
        # Tier 3: unmatched UBS -> type_median_fallback over [10, 20, 30] -> 20.0
        {
            "id": "UBS-4",
            "name": "US 888 UBS Desconhecida",
            "type": "UBS",
            "bairro": "AFOGADOS",
        },
        # Tier 3: unmatched USF (zero matched USFs) -> global_median_fallback over [10, 20, 30] -> 20.0
        {
            "id": "USF-1",
            "name": "US 777 USF Sem Estoque",
            "type": "USF",
            "bairro": "IBURA",
        },
    ]

    stock = [
        # Wrong bairro for US 121
        StockSummary("US 121 Farmacia Outro", "BOA VIAGEM", 99, 100, "2024-10-10"),
        # Correct bairro + name overlap for US 121
        StockSummary("US 121 CS Joaquim Cavalcanti", "Torrões", 10, 50, "2024-10-10"),
        # Same bairro, lower name overlap
        StockSummary("US 121 Policlínica", "Torrões", 77, 50, "2024-10-10"),
        StockSummary("US 103 CS Mario Ramos", "CASA AMARELA", 20, 60, "2024-10-10"),
        StockSummary("USF Sao Jose", "Sao Jose", 30, 80, "2024-10-10"),
    ]

    links = link_nodes_to_stock(nodes, stock)
    assert 0 not in links

    assert links[1].demand_match_method == "us_code"
    assert links[1].raw_stockouts == 10
    assert links[1].total_items == 50

    assert links[2].demand_match_method == "us_code"
    assert links[2].raw_stockouts == 20

    assert links[3].demand_match_method == "name_bairro"
    assert links[3].raw_stockouts == 30

    assert links[4].demand_match_method == "type_median_fallback"
    assert links[4].raw_stockouts is None
    assert links[4].total_items is None
    assert links[4].imputed_stockouts == 20.0
    assert links[4].raw_proxy == 20.0

    assert links[5].demand_match_method == "global_median_fallback"
    assert links[5].imputed_stockouts == 20.0


def test_link_nodes_to_stock_raises_when_zero_units_match() -> None:
    nodes = [
        {"id": "DEPOT-CAF", "name": "CAF", "type": "DEPOT", "bairro": "Bongi"},
        {"id": "UBS-1", "name": "US 100 Unidade A", "type": "UBS", "bairro": "Recife"},
    ]
    stock = [
        StockSummary("US 999 Unidade B", "Boa Viagem", 5, 10, "2024-10-10"),
    ]
    with pytest.raises(ValueError, match="Zero customer health units matched"):
        link_nodes_to_stock(nodes, stock)


def test_scale_demands_minmax_varying_and_degenerate() -> None:
    # Varying counts: [80, 145, 210] -> [10, 25, 40]
    assert scale_demands_minmax([80.0, 145.0, 210.0], d_min=10, d_max=40, capacity=100) == [
        10,
        25,
        40,
    ]

    # Degenerate equal counts: no ZeroDivisionError, all in [d_min, d_max]
    constant = scale_demands_minmax([50.0, 50.0, 50.0], d_min=10, d_max=40, capacity=100)
    assert len(constant) == 3
    assert all(isinstance(d, int) and 10 <= d <= 40 for d in constant)


@pytest.mark.parametrize(
    ("d_min", "d_max", "capacity"),
    [
        (0, 40, 100),
        (45, 40, 100),
        (10, 101, 100),
    ],
)
def test_scale_demands_minmax_rejects_invalid_bounds(
    d_min: int, d_max: int, capacity: int
) -> None:
    with pytest.raises(ValueError, match="Invalid demand scaling bounds"):
        scale_demands_minmax([10.0, 20.0], d_min=d_min, d_max=d_max, capacity=capacity)


def test_assign_empirical_demands_populates_nodes_and_metadata() -> None:
    nodes = [
        {"id": "DEPOT-CAF", "name": "CAF", "type": "DEPOT", "bairro": "Bongi", "demand": 0},
        {"id": "UBS-1", "name": "US 101 Unidade A", "type": "UBS", "bairro": "Recife"},
        {"id": "UBS-2", "name": "US 102 Unidade B", "type": "UBS", "bairro": "Recife"},
        {"id": "UBS-3", "name": "US 999 Unidade C", "type": "UBS", "bairro": "Recife"},
    ]
    stock = [
        StockSummary("US 101 Unidade A", "Recife", 10, 100, "2024-10-10"),
        StockSummary("US 102 Unidade B", "Recife", 30, 120, "2024-10-10"),
    ]

    metadata = assign_empirical_demands(nodes, stock, d_min=10, d_max=40, capacity=100)

    assert nodes[0]["demand"] == 0
    assert "raw_stockouts" not in nodes[0]

    assert nodes[1]["demand"] == 10
    assert nodes[1]["raw_stockouts"] == 10
    assert nodes[1]["total_items"] == 100
    assert nodes[1]["demand_match_method"] == "us_code"
    assert "imputed_stockouts" not in nodes[1]

    assert nodes[2]["demand"] == 40
    assert nodes[2]["raw_stockouts"] == 30
    assert nodes[2]["total_items"] == 120

    # Unmatched UBS-3 gets median(10, 30) = 20.0 -> scaled 25
    assert nodes[3]["demand"] == 25
    assert nodes[3]["raw_stockouts"] is None
    assert nodes[3]["total_items"] is None
    assert nodes[3]["demand_match_method"] == "type_median_fallback"
    assert nodes[3]["imputed_stockouts"] == 20.0

    assert metadata["method"] == "stockout_count_minmax"
    assert metadata["data_carga"] == "2024-10-10"
    assert metadata["d_min"] == 10
    assert metadata["d_max"] == 40
    assert metadata["raw_min"] == 10
    assert metadata["raw_max"] == 30
    assert metadata["match_summary"] == {
        "us_code": 2,
        "name_bairro": 0,
        "type_median_fallback": 1,
        "global_median_fallback": 0,
    }


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def test_fetch_osrm_matrix_raises_on_request_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fail(*args, **kwargs):
        raise requests.ConnectionError("network down")

    monkeypatch.setattr(requests, "get", _fail)
    coords = np.array([[-8.05, -34.92], [-8.06, -34.88]], dtype=np.float64)
    with pytest.raises(RuntimeError, match="OSRM road matrix request failed"):
        _fetch_osrm_matrix(coords)


def test_fetch_osrm_matrix_raises_on_non_ok_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        requests,
        "get",
        lambda *args, **kwargs: _FakeResponse({"code": "InvalidQuery"}),
    )
    coords = np.array([[-8.05, -34.92], [-8.06, -34.88]], dtype=np.float64)
    with pytest.raises(RuntimeError, match="OSRM returned invalid table response"):
        _fetch_osrm_matrix(coords)


def test_fetch_osrm_matrix_raises_on_unreachable_none_cell(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        requests,
        "get",
        lambda *args, **kwargs: _FakeResponse(
            {"code": "Ok", "distances": [[0.0, None], [1500.0, 0.0]]}
        ),
    )
    coords = np.array([[-8.05, -34.92], [-8.06, -34.88]], dtype=np.float64)
    with pytest.raises(RuntimeError, match="unreachable \\(None\\) distance"):
        _fetch_osrm_matrix(coords)


def test_fetch_osrm_matrix_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        requests,
        "get",
        lambda *args, **kwargs: _FakeResponse(
            {"code": "Ok", "distances": [[0.0, 2500.0], [2700.0, 0.0]]}
        ),
    )
    coords = np.array([[-8.05, -34.92], [-8.06, -34.88]], dtype=np.float64)
    mat = _fetch_osrm_matrix(coords)
    assert np.allclose(mat, np.array([[0.0, 2.5], [2.7, 0.0]]))


def _make_unit_row(
    *,
    cnes: str,
    nome_oficial: str,
    bairro: str,
    rpa: str,
    lat: float,
    lon: float,
) -> dict[str, str]:
    return {
        "cnes": cnes,
        "nome_oficial": nome_oficial,
        "bairro": bairro,
        "rpa": rpa,
        "latitude": f"{lat:.6f}",
        "longitude": f"{lon:.6f}",
    }


def test_select_recife_nodes_deduplicates_shifted_us_codes() -> None:
    ubs_rows = [
        _make_unit_row(
            cnes="0001551",
            nome_oficial="US 155 CS Romildo Gomes",
            bairro="BONGI",
            rpa="5",
            lat=-8.06000,
            lon=-34.92000,
        ),
        _make_unit_row(
            cnes="0001211",
            nome_oficial="US 121 CS Joaquim Cavalcanti",
            bairro="TORROES",
            rpa="4",
            lat=-8.05000,
            lon=-34.93000,
        ),
        _make_unit_row(
            cnes="0001371",
            nome_oficial="US 137 CS Gaspar Regueira Costa",
            bairro="BARRO",
            rpa="5",
            lat=-8.09000,
            lon=-34.94000,
        ),
    ]
    usf_rows = [
        # Shifted coordinates (~20-30 m) + placeholder CNES 9999999 for US 155, 121, 137
        _make_unit_row(
            cnes="9999999",
            nome_oficial="US 155 USF Romildo Gomes",
            bairro="BONGI",
            rpa="5",
            lat=-8.06020,
            lon=-34.92018,
        ),
        _make_unit_row(
            cnes="9999999",
            nome_oficial="US 121 USF Joaquim Cavalcanti",
            bairro="TORROES",
            rpa="4",
            lat=-8.05022,
            lon=-34.93015,
        ),
        _make_unit_row(
            cnes="9999999",
            nome_oficial="US 137 USF Gaspar Regueira",
            bairro="BARRO",
            rpa="5",
            lat=-8.09019,
            lon=-34.94020,
        ),
        # Distinct replacement USF
        _make_unit_row(
            cnes="2711223",
            nome_oficial="US 201 USF Coelhos",
            bairro="COELHOS",
            rpa="1",
            lat=-8.07000,
            lon=-34.89000,
        ),
    ]

    nodes = select_recife_nodes(ubs_rows, usf_rows, target_customers=4)
    assert len(nodes) == 5
    customers = nodes[1:]
    assert [n["id"] for n in customers] == [
        "UBS-0001551",
        "UBS-0001211",
        "UBS-0001371",
        "USF-2711223",
    ]
    us_codes = [extract_us_code(n["name"]) for n in customers]
    assert len(us_codes) == len(set(us_codes))


def test_select_recife_nodes_deduplicates_valid_cnes_and_name_bairro() -> None:
    ubs_rows = [
        _make_unit_row(
            cnes="1234567",
            nome_oficial="UBS Unidade Central",
            bairro="RECIFE",
            rpa="1",
            lat=-8.05500,
            lon=-34.88000,
        ),
        _make_unit_row(
            cnes="7654321",
            nome_oficial="UBS São José",
            bairro="SÃO JOSÉ",
            rpa="1",
            lat=-8.06500,
            lon=-34.88500,
        ),
    ]
    usf_rows = [
        # Duplicate via valid CNES despite different name and shifted coords
        _make_unit_row(
            cnes="1234567",
            nome_oficial="USF Nome Diferente",
            bairro="OUTRO",
            rpa="1",
            lat=-8.05550,
            lon=-34.88050,
        ),
        # Duplicate via normalized (name, bairro) despite different/placeholder CNES and shifted coords
        _make_unit_row(
            cnes="9999999",
            nome_oficial="USF Sao Jose",
            bairro="Sao Jose",
            rpa="1",
            lat=-8.06540,
            lon=-34.88540,
        ),
        # Distinct USF
        _make_unit_row(
            cnes="2222222",
            nome_oficial="USF Nova Esperança",
            bairro="IBURA",
            rpa="6",
            lat=-8.11000,
            lon=-34.95000,
        ),
    ]

    nodes = select_recife_nodes(ubs_rows, usf_rows, target_customers=3)
    assert [n["id"] for n in nodes[1:]] == ["UBS-1234567", "UBS-7654321", "USF-2222222"]


def test_select_recife_nodes_preserves_distinct_nearby_facilities() -> None:
    # ~45.5 m apart (like US 112 and US 225 in Iputinga)
    ubs_rows = [
        _make_unit_row(
            cnes="0001813",
            nome_oficial="US 112 UBS Iputinga",
            bairro="IPUTINGA",
            rpa="4",
            lat=-8.03400,
            lon=-34.93500,
        ),
    ]
    usf_rows = [
        _make_unit_row(
            cnes="0022306",
            nome_oficial="US 225 USF Vila União",
            bairro="IPUTINGA",
            rpa="4",
            lat=-8.03435,
            lon=-34.93520,
        ),
    ]

    nodes = select_recife_nodes(ubs_rows, usf_rows, target_customers=2)
    assert [n["id"] for n in nodes[1:]] == ["UBS-0001813", "USF-0022306"]


def test_select_recife_nodes_placeholder_cnes_gets_unique_ids() -> None:
    usf_rows = [
        _make_unit_row(
            cnes="9999999",
            nome_oficial="US 301 USF Alto Santa Terezinha",
            bairro="ALTO SANTA TEREZINHA",
            rpa="2",
            lat=-8.01000,
            lon=-34.90000,
        ),
        _make_unit_row(
            cnes="0000000",
            nome_oficial="USF Sem Codigo A",
            bairro="VARZEA",
            rpa="4",
            lat=-8.04500,
            lon=-34.96000,
        ),
        _make_unit_row(
            cnes="",
            nome_oficial="USF Sem Codigo B",
            bairro="COHAB",
            rpa="6",
            lat=-8.12000,
            lon=-34.95000,
        ),
    ]

    nodes = select_recife_nodes([], usf_rows, target_customers=3)
    ids = [n["id"] for n in nodes[1:]]
    assert len(ids) == 3
    assert len(set(ids)) == 3
    assert all("9999999" not in node_id and "0000000" not in node_id for node_id in ids)
    assert "USF-US301" in ids
