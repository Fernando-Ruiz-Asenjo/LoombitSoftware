"""Endpoint POST /galaxia/act: resuelve el arrastre y enruta los efectos al agente."""

from __future__ import annotations

from fastapi.testclient import TestClient

from loombit_operator.main import app


def test_act_local_no_crea_run() -> None:
    client = TestClient(app)
    r = client.post(
        "/galaxia/act",
        json={
            "source": {"kind": "documento", "etiqueta": "f.pdf", "path": "x"},
            "target": {"tipo": "cuenta", "etiqueta": "Acme", "id": "f:1"},
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["action"]["action_id"] == "adjuntar_doc_cuenta"
    assert body["action"]["efecto_externo"] is False
    assert "run_id" not in body  # local → no toca al agente


def test_act_efecto_externo_crea_run(monkeypatch) -> None:
    from loombit_operator.routers import agent as agent_router

    class _FakeRun:
        id = "run-x"

    class _FakeLoop:
        def create(self, task, profile="administrativo"):
            return _FakeRun()

        def execute_run(self, run_id):
            pass

    monkeypatch.setattr(agent_router, "_get_loop", lambda: _FakeLoop())

    client = TestClient(app)
    r = client.post(
        "/galaxia/act",
        json={
            "source": {"kind": "documento", "etiqueta": "f.pdf", "path": "x"},
            "target": {"tipo": "contacto", "etiqueta": "Jana", "email": "j@x.com"},
        },
    )
    body = r.json()
    assert body["action"]["efecto_externo"] is True
    assert body["run_id"] == "run-x"  # se creó el run del agente (que pedirá aprobación)
