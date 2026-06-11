"""
Router de «Loombit Decide»: la cola sale por la API con su spec de UI GOBERNADA (validada), y el
humano la resuelve. Verifica el CABLEADO HTTP (que el backend nunca emite una spec sin validar y que
resolver registra la opción elegida).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from loombit_operator.decisions import (
    Decision,
    DecisionKind,
    DecisionOption,
    DecisionStore,
    OptionKind,
    Risk,
)
from loombit_operator.main import app
from loombit_operator.routers import decisions as decisions_router
from loombit_operator.ui_spec import validate_spec

client = TestClient(app)


@pytest.fixture
def store_aislado(tmp_path, monkeypatch):
    path = tmp_path / "decisions.json"
    monkeypatch.setattr(decisions_router, "DecisionStore", lambda: DecisionStore(store_path=path))
    return DecisionStore(store_path=path)


def _cobro():
    return Decision(
        title="Reclamar cobro a Acme · 1.210 € VENCIDA",
        why="Vencida hace 12 días.",
        kind=DecisionKind.COBRO,
        risk=Risk.MEDIO,
        options=[
            DecisionOption(id="aprobar", label="Aprobar y enviar", kind=OptionKind.APROBAR),
            DecisionOption(id="posponer", label="Posponer", kind=OptionKind.POSPONER),
        ],
    )


def test_cola_devuelve_spec_validada(store_aislado):
    store_aislado.add(_cobro())
    data = client.get("/decisions").json()
    assert data["count"] == 1
    assert data["spec"]["type"] == "cola"
    ok, errores = validate_spec(data["spec"])
    assert ok, errores  # el backend NUNCA emite una spec sin validar
    assert data["spec"]["items"][0]["type"] == "decision_card"


def test_resolver_por_api(store_aislado):
    d = store_aislado.add(_cobro())
    r = client.post(f"/decisions/{d.id}/resolve", json={"option_id": "aprobar"})
    assert r.status_code == 200
    assert r.json()["decision"]["status"] == "resuelta"
    assert r.json()["decision"]["chosen_option"] == "aprobar"
    # ya no está en la cola
    assert client.get("/decisions").json()["count"] == 0


def test_resolver_opcion_invalida_da_400(store_aislado):
    d = store_aislado.add(_cobro())
    r = client.post(f"/decisions/{d.id}/resolve", json={"option_id": "borrar_todo"})
    assert r.status_code == 400


def test_decision_inexistente_da_404(store_aislado):
    assert client.get("/decisions/no-existe").status_code == 404


# ── LD-2: sembrar desde cobros + APROBAR lanza la acción al gate ──────────────


def test_sembrar_cobros_encola_decisiones(tmp_path, monkeypatch):
    from datetime import date, timedelta

    import loombit_operator.cuentas_cobrar as cc_mod
    from loombit_operator.cuentas_cobrar import CuentaCobrar, CuentasCobrarStore

    dpath = tmp_path / "decisions.json"
    ccpath = tmp_path / "cc.json"
    monkeypatch.setattr(decisions_router, "DecisionStore", lambda: DecisionStore(store_path=dpath))

    # se siembra con la clase real ANTES de parchear el módulo que usa el router
    venc = (date.today() - timedelta(days=20)).isoformat()
    CuentasCobrarStore(path=ccpath).add(
        CuentaCobrar(cliente="Acme", importe=1250, vencimiento=venc)
    )
    monkeypatch.setattr(cc_mod, "CuentasCobrarStore", lambda: CuentasCobrarStore(path=ccpath))

    r = client.post("/decisions/sembrar-cobros")
    assert r.status_code == 200 and r.json()["creadas"] == 1
    # idempotente: una segunda siembra no duplica
    assert client.post("/decisions/sembrar-cobros").json()["creadas"] == 0
    cola = client.get("/decisions").json()
    assert cola["count"] == 1 and cola["spec"]["items"][0]["type"] == "decision_card"


def test_aprobar_lanza_accion_al_gate(store_aislado, monkeypatch):
    lanzadas = []

    def _stub(task, background_tasks):
        lanzadas.append(task)
        return "run-fake-1"

    monkeypatch.setattr(decisions_router, "_lanzar_accion", _stub)

    d = store_aislado.add(_cobro())
    d.payload["agent_task"] = (
        "Prepara un recordatorio de cobro para Acme. No lo envíes sin que lo apruebe."
    )
    store_aislado.add(d)

    r = client.post(f"/decisions/{d.id}/resolve", json={"option_id": "aprobar"})
    assert r.status_code == 200
    assert r.json()["run_id"] == "run-fake-1"
    assert len(lanzadas) == 1 and "recordatorio" in lanzadas[0].lower()


def test_posponer_no_lanza_accion(store_aislado, monkeypatch):
    lanzadas = []
    monkeypatch.setattr(
        decisions_router, "_lanzar_accion", lambda task, bt: lanzadas.append(task) or "x"
    )
    d = store_aislado.add(_cobro())
    r = client.post(f"/decisions/{d.id}/resolve", json={"option_id": "posponer"})
    assert r.status_code == 200 and r.json()["run_id"] == ""
    assert lanzadas == []
