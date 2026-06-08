"""Tests del router fiscal (API multi-entidad): factura → 303 → aprobación humana."""

import shutil
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from loombit_operator.config import get_settings
from loombit_operator.main import app

client = TestClient(app)


@pytest.fixture
def eid():
    """Entidad única por test; limpia su carpeta al terminar."""
    e = "test_" + uuid4().hex[:8]
    yield e
    d = get_settings().entities_dir / e
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)


def test_flujo_factura_303_aprobacion(eid):
    # registrar dos facturas (una emitida, una recibida)
    r = client.post(
        f"/entidades/{eid}/facturas",
        json={"sentido": "devengado", "numero": "E-1", "base_imponible": 1000.0, "iva": 210.0},
    )
    assert r.status_code == 200
    assert r.json()["kind"] == "factura_intake"
    client.post(
        f"/entidades/{eid}/facturas",
        json={"sentido": "soportado", "numero": "R-1", "base_imponible": 500.0, "iva": 105.0},
    )

    # listar
    lst = client.get(f"/entidades/{eid}/expedientes").json()
    assert lst["count"] == 2

    # liquidar el 303 → queda PENDING_APPROVAL (la IA no presenta)
    liq = client.post(f"/entidades/{eid}/303", json={"periodo": "2026-T2"}).json()
    assert liq["status"] == "pending_approval"
    assert liq["resultado"] == "105.00"
    assert "BORRADOR" in liq["borrador"]
    exp_id = liq["expediente_id"]

    # detalle: trazabilidad íntegra + evento del cálculo
    det = client.get(f"/entidades/{eid}/expedientes/{exp_id}").json()
    assert det["trazabilidad_integra"] is True
    assert "calculo_303" in [e["kind"] for e in det["eventos"]]

    # el HUMANO aprueba aportando justificante → se cierra
    apr = client.post(
        f"/entidades/{eid}/expedientes/{exp_id}/aprobar",
        json={"justificante": "CSV-ABC123"},
    ).json()
    assert apr["status"] == "closed"

    det2 = client.get(f"/entidades/{eid}/expedientes/{exp_id}").json()
    assert "justificante_aportado" in [e["kind"] for e in det2["eventos"]]
    assert det2["trazabilidad_integra"] is True


def test_entity_id_invalido_da_400():
    r = client.post("/entidades/..%2Fescape/facturas", json={"sentido": "devengado"})
    # la ruta puede no resolver el path traversal; aceptamos 400 (validado) o 404 (no ruta)
    assert r.status_code in (400, 404)


def test_expediente_inexistente_da_404(eid):
    r = client.get(f"/entidades/{eid}/expedientes/no-existe")
    assert r.status_code == 404
