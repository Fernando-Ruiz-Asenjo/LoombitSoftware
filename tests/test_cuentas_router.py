"""
Router de cuentas a cobrar: una factura vencida sale ya con su PLAN de cobro (saldo, etapa,
compensación de 40 € e interés de demora). El cálculo exacto del interés se prueba en
test_tipos_demora / test_telar; aquí se verifica el CABLEADO (que el plan llega por la API).
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from loombit_operator.cuentas_cobrar import CuentasCobrarStore
from loombit_operator.main import app
from loombit_operator.routers import cuentas as cuentas_router

client = TestClient(app)


@pytest.fixture
def store_aislado(tmp_path, monkeypatch):
    """Apunta el router a un store en tmp_path para no tocar el runtime real."""
    path = tmp_path / "cuentas_cobrar.json"
    monkeypatch.setattr(cuentas_router, "CuentasCobrarStore", lambda: CuentasCobrarStore(path=path))
    return path


def test_vencida_llega_con_plan_de_cobro(store_aislado):
    venc = (date.today() - timedelta(days=20)).isoformat()  # 20 días vencida
    r = client.post("/cuentas", json={"cliente": "Acme", "importe": 1250.0, "vencimiento": venc})
    assert r.status_code == 200
    cuenta_id = r.json()["id"]

    data = client.get("/cuentas").json()
    assert data["vencidas"], "la cuenta vencida debería aparecer"
    plan = data["vencidas"][0]["plan"]
    assert plan["action"] == "reclamar"
    assert plan["fixed_compensation_eur"] == 40.0
    assert (
        "rate_required" in plan["interest"]
    )  # interés resuelto o abstención, pero SIEMPRE presente

    # endpoint dedicado del plan de una cuenta
    p = client.get(f"/cuentas/{cuenta_id}/plan")
    assert p.status_code == 200
    assert p.json()["plan"]["action"] == "reclamar"


def test_plan_de_cuenta_inexistente_es_404(store_aislado):
    assert client.get("/cuentas/noexiste/plan").status_code == 404
