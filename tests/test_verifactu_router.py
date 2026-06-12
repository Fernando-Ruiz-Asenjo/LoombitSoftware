"""
Router del libro VeriFactu — golden de CABLEADO con dientes.

GET /verifactu/registros lista los registros con su huella y marca íntegro=True; GET /verifactu/verificar
detecta una manipulación del fichero (íntegro→False). El alta se prueba en test_verifactu_store /
test_intake_batch; aquí se verifica que la API lee y verifica el libro real.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from loombit_operator.docs_intel import InvoiceFields
from loombit_operator.main import app
from loombit_operator.routers import verifactu as verifactu_router
from loombit_operator.skill_d_fiscal.verifactu_store import RegistroVerifactuStore

client = TestClient(app)
NIF = "B12345678"


@pytest.fixture
def libro_aislado(tmp_path, monkeypatch):
    """Apunta el router a un libro en tmp_path con dos registros encadenados (no toca el runtime real)."""
    p = tmp_path / "vf.jsonl"
    monkeypatch.setattr(
        verifactu_router, "RegistroVerifactuStore", lambda: RegistroVerifactuStore(path=p)
    )
    store = RegistroVerifactuStore(path=p)
    store.registrar(InvoiceFields(numero="F-1", fecha="2026-05-10", total=1210.0, nif=NIF), NIF)
    store.registrar(InvoiceFields(numero="F-2", fecha="2026-05-11", total=2420.0, nif=NIF), NIF)
    return p


def test_registros_lista_integro(libro_aislado):
    data = client.get("/verifactu/registros").json()
    assert data["count"] == 2 and data["integro"] is True
    assert data["registros"][1]["huella_anterior"] == data["registros"][0]["huella"]


def test_verificar_detecta_manipulacion(libro_aislado):
    assert client.get("/verifactu/verificar").json() == {"ok": True, "errores": []}
    # Alterar a mano el importe del primer registro sin recomputar su huella.
    lineas = libro_aislado.read_text(encoding="utf-8").splitlines()
    d0 = json.loads(lineas[0])
    d0["importe_total"] = 9999.0
    lineas[0] = json.dumps(d0, ensure_ascii=False)
    libro_aislado.write_text("\n".join(lineas) + "\n", encoding="utf-8")

    out = client.get("/verifactu/verificar").json()
    assert out["ok"] is False and out["errores"]  # la manipulación se DETECTA por la API
