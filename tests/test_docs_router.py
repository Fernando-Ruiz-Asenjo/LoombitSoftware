"""
Tests del router de inteligencia documental (/docs-intel/invoice): extracción,
gate antifraude de IBAN y cruce con albarán. La memoria se aísla en tmp.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from loombit_operator.agent.memory import AgentMemory
from loombit_operator.main import app

client = TestClient(app)

INVOICE = """\
Suministros Norte S.L.
CIF: B12345678
Factura Nº: 2026/0050
Fecha de factura: 01/06/2026
Vencimiento: 01/07/2026
Total a pagar 1.210,00 €
IBAN: ES99 9999 9999 9999 9999 9999
"""


def test_invoice_requires_input():
    resp = client.post("/docs-intel/invoice", json={})
    assert resp.status_code == 400


def test_invoice_extracts_without_learning(tmp_path):
    mem = AgentMemory(store_path=tmp_path / "m.json")
    with patch("loombit_operator.routers.docs.get_memory", return_value=mem):
        resp = client.post("/docs-intel/invoice", json={"text": INVOICE, "learn": False})
    assert resp.status_code == 200
    data = resp.json()
    f = data["fields"]
    assert f["nif"] == "B12345678"
    assert f["numero"] == "2026/0050"
    assert f["total"] == 1210.0
    assert "Suministros Norte" in data["result"]


def test_invoice_iban_fraud_gate(tmp_path):
    mem = AgentMemory(store_path=tmp_path / "m.json")
    # Proveedor conocido con un IBAN legítimo previo.
    mem.upsert_entity(
        "Suministros Norte S.L.", nif="B12345678", iban="ES11 1111 1111 1111 1111 1111"
    )

    with patch("loombit_operator.routers.docs.get_memory", return_value=mem):
        resp = client.post("/docs-intel/invoice", json={"text": INVOICE})  # IBAN distinto
    data = resp.json()

    assert data["iban_check"]["is_new_for_known_entity"] is True
    assert any("fraude" in w.lower() for w in data["warnings"])
    # El IBAN sospechoso NO se aprende.
    assert (
        mem.is_known_iban(
            "Suministros Norte S.L.", "ES99 9999 9999 9999 9999 9999", nif="B12345678"
        )
        is False
    )
    assert (
        mem.is_known_iban(
            "Suministros Norte S.L.", "ES11 1111 1111 1111 1111 1111", nif="B12345678"
        )
        is True
    )


def test_invoice_learns_new_supplier(tmp_path):
    mem = AgentMemory(store_path=tmp_path / "m.json")
    with patch("loombit_operator.routers.docs.get_memory", return_value=mem):
        resp = client.post("/docs-intel/invoice", json={"text": INVOICE})
    assert resp.json()["learned_entity"] is True
    # Proveedor nuevo: su primer IBAN sí se aprende (no había nada que comparar).
    assert (
        mem.is_known_iban(
            "Suministros Norte S.L.", "ES99 9999 9999 9999 9999 9999", nif="B12345678"
        )
        is True
    )


def test_invoice_cross_check_albaran_mismatch(tmp_path):
    mem = AgentMemory(store_path=tmp_path / "m.json")
    with patch("loombit_operator.routers.docs.get_memory", return_value=mem):
        resp = client.post(
            "/docs-intel/invoice",
            json={"text": INVOICE, "learn": False, "albaran_total": 1000.0},
        )
    data = resp.json()
    assert data["cross_check"]["match"] is False
    assert any("albarán" in w.lower() for w in data["warnings"])
