"""
Router del lazo de cobros (pieza 3) — golden de CABLEADO con dientes.

Prueba que la API cierra el lazo sin saltarse el gate: GET /cobros/pendientes solo LISTA (no escribe
nada), POST /cobros/aprobar de una cuenta vencida deja UN recordatorio en el outbox y devuelve recibo,
y una cuenta inexistente/no vencida es 404. El gate sagrado (sin aprobación no sale nada) y las cifras
por código se prueban a nivel unidad en test_cobros_flujo / test_envio_cobro; aquí se verifica el cableado.
"""

from __future__ import annotations

import functools
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from loombit_operator.cuentas_cobrar import CuentaCobrar, CuentasCobrarStore
from loombit_operator.main import app
from loombit_operator.routers import cobros as cobros_router
from loombit_operator.skill_d_fiscal import cobros_flujo

client = TestClient(app)


@pytest.fixture
def store_aislado(tmp_path, monkeypatch):
    """Apunta el router a un store y un outbox en tmp_path (no toca el runtime real ni envía nada)."""
    path = tmp_path / "cuentas_cobrar.json"
    outbox = tmp_path / "outbox"
    monkeypatch.setattr(cobros_router, "CuentasCobrarStore", lambda: CuentasCobrarStore(path=path))
    # El envío real sigue pasando por el gate; solo redirigimos el outbox a tmp_path (función REAL).
    monkeypatch.setattr(
        cobros_router,
        "aprobar_y_enviar",
        functools.partial(cobros_flujo.aprobar_y_enviar, outbox_dir=outbox),
    )
    store = CuentasCobrarStore(path=path)
    venc = (date.today() - timedelta(days=20)).isoformat()  # 20 días vencida
    cuenta = store.add(CuentaCobrar(cliente="Acme SL", importe=1250.0, vencimiento=venc))
    return cuenta, outbox


def test_pendientes_lista_sin_enviar(store_aislado):
    _cuenta, outbox = store_aislado
    data = client.get("/cobros/pendientes").json()
    assert data["count"] == 1
    assert data["pendientes"][0]["cuenta_id"]  # cada decisión enlaza su cuenta para poder aprobarla
    assert not outbox.exists()  # LISTAR no envía: el outbox no se crea


def test_aprobar_envia_un_recordatorio_al_outbox(store_aislado):
    cuenta, outbox = store_aislado
    r = client.post("/cobros/aprobar", json={"cuenta_id": cuenta.id})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and body["recibo"]["enviado"] is True
    assert body["recibo"]["via"] == "outbox"
    assert len(list(outbox.glob("*.eml"))) == 1  # exactamente UN recordatorio


def test_aprobar_cuenta_inexistente_es_404(store_aislado):
    assert client.post("/cobros/aprobar", json={"cuenta_id": "noexiste"}).status_code == 404
