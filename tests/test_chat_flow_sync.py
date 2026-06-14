"""
Regresión del fallo del chat (captura de Fernando, 2026-06-08): al responder una pregunta o aprobar
una acción, el run se quedaba en su estado VIEJO al volver la respuesta → la UI re-pintaba la misma
pregunta/tarjeta y, en la carrera, la 2ª respuesta caía en un run ya `pending_approval`
("Error al responder: ... status=pending_approval").

Arreglo: `accept_answer` / `accept_approval` ACEPTAN la acción de forma SÍNCRONA (run → running) sin
ejecutar el LLM; la continuación va a background. Aquí se prueba esa transición síncrona.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from loombit_operator.agent.loop import AgentLoop
from loombit_operator.agent.run import AgentRun, AgentStatus, AgentStep, AgentStore
from loombit_operator.tools.registry import ToolDefinition, ToolRegistry


class _LLMQueExplota:
    """Si el flujo síncrono llamara al LLM, este doble lo delataría reventando."""

    def chat(self, *a, **k):
        raise AssertionError("accept_* NO debe invocar al LLM (eso es trabajo de background)")


def _loop(registry: ToolRegistry, tmp_path) -> AgentLoop:
    return AgentLoop(
        llm=_LLMQueExplota(),
        registry=registry,
        store=AgentStore(store_path=tmp_path / "runs.json"),
    )


# ── accept_answer ───────────────────────────────────────────────────────────────


def test_accept_answer_pasa_a_running_sin_llamar_al_llm(tmp_path):
    loop = _loop(ToolRegistry(), tmp_path)
    run = AgentRun(task="¿cuándo es la reunión?")
    run.messages = [
        {"role": "assistant", "content": None},
        {"role": "tool", "tool_call_id": "tcQ", "content": "PENDING_QUESTION:{}"},
    ]
    run.steps = [
        AgentStep(
            step=1,
            tool_name="ask_user",
            tool_call_id="tcQ",
            arguments={},
            result="PENDING_QUESTION:{}",
            requires_approval=True,
        )
    ]
    run.mark_pending_question(question="¿Hora exacta?", tool_call_id="tcQ")
    loop.store.save_run(run)

    out = loop.accept_answer(run.id, "a las 9 de la mañana")

    assert (
        out.status is AgentStatus.RUNNING
    )  # ya NO pending_question → la UI no re-pinta la pregunta
    assert out.pending_question == {}
    # la respuesta quedó inyectada en el sitio de la pregunta y como mensaje de usuario
    assert out.steps[0].result == "Usuario respondió: a las 9 de la mañana"
    assert out.messages[-1] == {"role": "user", "content": "a las 9 de la mañana"}
    # y persistido en el store
    assert loop.store.get(run.id).status is AgentStatus.RUNNING


def test_accept_answer_falla_si_no_esta_en_pending_question(tmp_path):
    loop = _loop(ToolRegistry(), tmp_path)
    run = AgentRun(task="x")
    run.mark_pending_approval(reason="r", proposed_action="a", tool_call_id="t")
    loop.store.save_run(run)
    with pytest.raises(ValueError, match="pending_question"):
        loop.accept_answer(run.id, "tarde")


# ── accept_approval ─────────────────────────────────────────────────────────────


def test_accept_approval_pasa_a_running_sin_ejecutar_la_tool(tmp_path):
    ejecutada = {"si": False}

    def _marca(**_):
        ejecutada["si"] = True
        return "ok"

    reg = ToolRegistry()
    reg.register(
        ToolDefinition(
            name="calendar_create",
            description="crea evento",
            parameters={"type": "object", "properties": {}},
            fn=_marca,
            requires_approval=True,
        )
    )
    loop = _loop(reg, tmp_path)
    run = AgentRun(task="crea un evento el jueves")
    run.messages = [{"role": "tool", "tool_call_id": "tcA", "content": "PENDING_APPROVAL:{}"}]
    run.steps = [
        AgentStep(
            step=1,
            tool_name="calendar_create",
            tool_call_id="tcA",
            arguments={"summary": "Reunión con David"},
            result="PENDING_APPROVAL:{}",
            requires_approval=True,
        )
    ]
    run.mark_pending_approval(reason="crear evento", proposed_action="...", tool_call_id="tcA")
    loop.store.save_run(run)

    out = loop.accept_approval(run.id)

    assert (
        out.status is AgentStatus.RUNNING
    )  # ya NO pending_approval → la UI no re-pinta la tarjeta
    assert out.pending_approval == {}
    assert ejecutada["si"] is False  # la tool aún NO se ejecutó (eso es trabajo de _resume_execute)
    # el step sigue marcado para que _resume_execute lo ejecute después
    assert out.steps[0].requires_approval is True


def test_accept_approval_falla_si_no_esta_en_pending_approval(tmp_path):
    loop = _loop(ToolRegistry(), tmp_path)
    run = AgentRun(task="x")
    run.mark_pending_question(question="¿?", tool_call_id="t")
    loop.store.save_run(run)
    with pytest.raises(ValueError, match="pending_approval"):
        loop.accept_approval(run.id)


def test_resume_execute_ejecuta_la_tool_aprobada(tmp_path, monkeypatch):
    """Tras aceptar, _resume_execute SÍ ejecuta la tool aprobada. La continuación del LLM la captura
    `_execute` (el doble revienta → run failed), pero lo que validamos es que la tool corrió."""
    monkeypatch.setattr(
        "loombit_operator.agent.memory.get_memory", lambda: MagicMock()
    )  # sin tocar memoria real
    ejecutada = {"si": False}

    def _marca(**_):
        ejecutada["si"] = True
        return "EVENTO_CREADO"

    reg = ToolRegistry()
    reg.register(
        ToolDefinition(
            name="calendar_create",
            description="crea evento",
            parameters={"type": "object", "properties": {}},
            fn=_marca,
            requires_approval=True,
        )
    )
    loop = _loop(reg, tmp_path)
    run = AgentRun(task="crea un evento")
    run.messages = [{"role": "tool", "tool_call_id": "tcA", "content": "PENDING_APPROVAL:{}"}]
    run.steps = [
        AgentStep(
            step=1,
            tool_name="calendar_create",
            tool_call_id="tcA",
            arguments={},
            result="PENDING_APPROVAL:{}",
            requires_approval=True,
        )
    ]
    run.mark_pending_approval(reason="r", proposed_action="a", tool_call_id="tcA")
    loop.store.save_run(run)

    loop.accept_approval(run.id)
    out = loop._resume_execute(run.id)  # ejecuta la tool; la continuación LLM falla y se captura

    assert ejecutada["si"] is True  # la tool aprobada SÍ se ejecutó
    assert out.steps[0].result == "EVENTO_CREADO" and out.steps[0].requires_approval is False


# ── Regresión a nivel HTTP (el bug exacto de la captura) ────────────────────────


def _seed_router(monkeypatch, tmp_path, registry=None):
    """Inyecta un store+loop controlados en el router del agente; stubbea el trabajo de background
    para que el test no toque el LLM."""
    from loombit_operator.routers import agent as agent_router

    store = AgentStore(store_path=tmp_path / "runs.json")
    loop = AgentLoop(llm=_LLMQueExplota(), registry=registry or ToolRegistry(), store=store)
    monkeypatch.setattr(loop, "execute_run", lambda run_id: store.get(run_id))
    monkeypatch.setattr(loop, "_resume_execute", lambda run_id: store.get(run_id))
    monkeypatch.setattr(agent_router, "_store", store)
    monkeypatch.setattr(agent_router, "_loop", loop)
    return store


def test_http_answer_devuelve_running_no_pending_question(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from loombit_operator.main import app

    store = _seed_router(monkeypatch, tmp_path)
    run = AgentRun(task="¿cuándo es la reunión con David?")
    run.messages = [{"role": "tool", "tool_call_id": "tcQ", "content": "PENDING_QUESTION:{}"}]
    run.steps = [
        AgentStep(
            step=1,
            tool_name="ask_user",
            tool_call_id="tcQ",
            arguments={},
            result="PENDING_QUESTION:{}",
            requires_approval=True,
        )
    ]
    run.mark_pending_question(question="¿Hora exacta?", tool_call_id="tcQ")
    store.save_run(run)

    r = TestClient(app).post(f"/agent/runs/{run.id}/answer", json={"answer": "a las 9"})
    assert r.status_code == 200
    # EL ARREGLO: antes devolvía "pending_question" (la UI re-pintaba la pregunta). Ahora "running".
    assert r.json()["status"] == "running"


def test_http_approve_devuelve_running_no_pending_approval(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from loombit_operator.main import app

    reg = ToolRegistry()
    reg.register(
        ToolDefinition(
            name="calendar_create",
            description="crea evento",
            parameters={"type": "object", "properties": {}},
            fn=lambda **_: "ok",
            requires_approval=True,
        )
    )
    store = _seed_router(monkeypatch, tmp_path, registry=reg)
    run = AgentRun(task="crea el evento")
    run.messages = [{"role": "tool", "tool_call_id": "tcA", "content": "PENDING_APPROVAL:{}"}]
    run.steps = [
        AgentStep(
            step=1,
            tool_name="calendar_create",
            tool_call_id="tcA",
            arguments={},
            result="PENDING_APPROVAL:{}",
            requires_approval=True,
        )
    ]
    run.mark_pending_approval(reason="r", proposed_action="a", tool_call_id="tcA")
    store.save_run(run)

    r = TestClient(app).post(f"/agent/runs/{run.id}/approve", json={"comment": ""})
    assert r.status_code == 200
    # EL ARREGLO: antes devolvía "pending_approval" (la UI re-pintaba la tarjeta). Ahora "running".
    assert r.json()["status"] == "running"
