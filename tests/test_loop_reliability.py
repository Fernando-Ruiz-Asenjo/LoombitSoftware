"""
Frente 2 — fiabilidad del agente (Investigación 6).

Dos garantías deterministas del bucle:
  A. Si la acción que el usuario YA APROBÓ falla al ejecutarse, `resume()` NO re-pausa en
     silencio: inyecta un aviso honesto para que el modelo lo corrija una vez o lo explique
     (el bug de "la ventanita de aprobación que reaparece sin decir por qué").
  B. Anti-flailing: si la MISMA tool falla 2 veces seguidas, el bucle corta en seco
     (`mark_failed`) en vez de quemar los 20 pasos martilleando algo roto. El 1er fallo avisa.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from loombit_operator.agent.loop import (
    AgentLoop,
    _consecutive_tool_errors,
    _error_brief,
    _is_error_result,
)
from loombit_operator.agent.run import AgentRun, AgentStatus, AgentStep, AgentStore
from loombit_operator.llm import ChatResponse, ToolCall
from loombit_operator.tools.registry import ToolDefinition, ToolRegistry

# ── Dobles de prueba ────────────────────────────────────────────────────────────


class _ScriptedLLM:
    """LLM falso: cada turno devuelve una respuesta de una lista; si se agota, repite la última.
    Una respuesta es ('tool', name, args) → tool_call, o ('done', texto) → stop con TASK_DONE."""

    def __init__(self, guion: list[tuple]) -> None:
        self.guion = guion
        self.turno = 0

    def chat(self, messages, tools=None, tool_choice=None, **_):
        spec = self.guion[min(self.turno, len(self.guion) - 1)]
        self.turno += 1
        if spec[0] == "tool":
            _, name, args = spec
            return ChatResponse(
                content="",
                tool_calls=[ToolCall(id=f"tc{self.turno}", tool_name=name, arguments=dict(args))],
                finish_reason="tool_calls",
            )
        return ChatResponse(content=f"TASK_DONE: {spec[1]}", finish_reason="stop")


def _tool(name: str, fn, requires_approval: bool = False) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        description=f"tool de prueba {name}",
        parameters={"type": "object", "properties": {}},
        fn=fn,
        requires_approval=requires_approval,
    )


@pytest.fixture
def _no_memory(monkeypatch):
    """Neutraliza la memoria persistente (reflexión / update) para no tocar disco real."""
    monkeypatch.setattr("loombit_operator.agent.memory.get_memory", lambda: MagicMock())


def _loop_con(registry: ToolRegistry, llm, tmp_path) -> AgentLoop:
    store = AgentStore(store_path=tmp_path / "runs.json")
    return AgentLoop(llm=llm, registry=registry, store=store, max_steps=20)


def _step(tool_name: str, result: str) -> AgentStep:
    return AgentStep(
        step=1,
        tool_name=tool_name,
        tool_call_id="x",
        arguments={},
        result=result,
        requires_approval=False,
    )


# ── Helpers deterministas ───────────────────────────────────────────────────────


def test_is_error_result_reconoce_los_prefijos_del_bucle():
    assert _is_error_result("ERROR: tool desconocida 'foo'")
    assert _is_error_result("ERROR: argumentos invalidos para 'foo': x")
    assert _is_error_result("ERROR en 'foo': boom")
    assert _is_error_result("ERROR al ejecutar 'foo': boom")
    # No son errores del bucle:
    assert not _is_error_result("[SISTEMA: aviso]")
    assert not _is_error_result("Todo correcto")
    assert not _is_error_result("")


def test_error_brief_recorta_a_una_linea():
    assert _error_brief("ERROR en 'x': boom\nsegunda linea") == "ERROR en 'x': boom"
    largo = "ERROR en 'x': " + "a" * 300
    assert _error_brief(largo).endswith("…") and len(_error_brief(largo)) <= 161


def test_consecutive_tool_errors_cuenta_seguidos_e_ignora_intercaladas():
    run = SimpleNamespace(
        steps=[
            _step("foo", "ERROR en 'foo': 1"),
            _step("bar", "ok"),  # otra tool intercalada → no rompe la racha de foo
            _step("foo", "ERROR en 'foo': 2"),
        ]
    )
    assert _consecutive_tool_errors(run, "foo") == 2
    assert _consecutive_tool_errors(run, "bar") == 0


def test_consecutive_tool_errors_se_resetea_tras_un_exito():
    run = SimpleNamespace(
        steps=[
            _step("foo", "ERROR en 'foo': 1"),
            _step("foo", "ok"),  # éxito → corta la racha
            _step("foo", "ERROR en 'foo': 2"),
        ]
    )
    assert _consecutive_tool_errors(run, "foo") == 1


# ── _maybe_cut_for_flailing (lógica de corte aislada) ───────────────────────────


def test_primer_fallo_avisa_pero_no_corta():
    loop = AgentLoop(llm=SimpleNamespace())
    run = SimpleNamespace(id="r", messages=[], steps=[_step("foo", "ERROR en 'foo': boom")])
    corte = loop._maybe_cut_for_flailing(run, [ToolCall(id="t", tool_name="foo", arguments={})])
    assert corte is None
    assert any("foo" in m["content"] and "2º fallo" in m["content"] for m in run.messages)


def test_segundo_fallo_seguido_corta():
    loop = AgentLoop(llm=SimpleNamespace())
    run = SimpleNamespace(
        id="r",
        messages=[],
        steps=[_step("foo", "ERROR en 'foo': 1"), _step("foo", "ERROR en 'foo': 2")],
    )
    corte = loop._maybe_cut_for_flailing(run, [ToolCall(id="t", tool_name="foo", arguments={})])
    assert corte is not None
    assert "foo" in corte and "2 veces" in corte


def test_tool_que_no_falla_no_corta():
    loop = AgentLoop(llm=SimpleNamespace())
    run = SimpleNamespace(id="r", messages=[], steps=[_step("foo", "todo bien")])
    assert (
        loop._maybe_cut_for_flailing(run, [ToolCall(id="t", tool_name="foo", arguments={})]) is None
    )
    assert run.messages == []


# ── Integración: el bucle entero corta de verdad ────────────────────────────────


def test_loop_corta_tool_que_revienta_dos_veces(tmp_path, _no_memory):
    def _revienta(**_):
        raise RuntimeError("se rompió")

    reg = ToolRegistry()
    reg.register(_tool("tool_rota", _revienta))
    llm = _ScriptedLLM([("tool", "tool_rota", {})])  # siempre llama a la tool rota
    loop = _loop_con(reg, llm, tmp_path)

    run = loop.store.create("usa tool_rota")
    run.messages = [{"role": "system", "content": "s"}, {"role": "user", "content": "go"}]
    out = loop.execute_run(run.id)

    assert out.status is AgentStatus.FAILED
    assert "tool_rota" in out.error and "2 veces" in out.error
    assert out.step_count == 2  # cortó al 2º fallo, no quemó los 20 pasos


def test_loop_corta_tool_inexistente_dos_veces(tmp_path, _no_memory):
    reg = ToolRegistry()  # vacío → cualquier tool es "desconocida"
    llm = _ScriptedLLM([("tool", "no_existe", {})])
    loop = _loop_con(reg, llm, tmp_path)

    run = loop.store.create("haz algo")
    run.messages = [{"role": "system", "content": "s"}, {"role": "user", "content": "go"}]
    out = loop.execute_run(run.id)

    assert out.status is AgentStatus.FAILED
    assert "no_existe" in out.error
    assert out.step_count == 2


def test_loop_no_corta_si_se_recupera(tmp_path, _no_memory):
    """1 fallo y luego task_done: el agente NO debe terminar en FAILED por anti-flailing."""
    estado = {"llamadas": 0}

    def _falla_una_vez(**_):
        estado["llamadas"] += 1
        if estado["llamadas"] == 1:
            raise RuntimeError("primer intento")
        return "ok"

    reg = ToolRegistry()
    reg.register(_tool("intermitente", _falla_una_vez))
    # turno 1: llama intermitente (falla) · turno 2: llama intermitente (ok) · turno 3: done
    llm = _ScriptedLLM(
        [("tool", "intermitente", {}), ("tool", "intermitente", {}), ("done", "listo")]
    )
    loop = _loop_con(reg, llm, tmp_path)

    run = loop.store.create("usa intermitente")
    run.messages = [{"role": "system", "content": "s"}, {"role": "user", "content": "go"}]
    out = loop.execute_run(run.id)

    assert out.status is AgentStatus.COMPLETED  # se recuperó, no se cortó


# ── Integración: resume surfacea el fallo de una acción aprobada ────────────────


def test_resume_surfacea_fallo_de_accion_aprobada(tmp_path, _no_memory):
    def _revienta(**_):
        raise RuntimeError("token caducado")

    reg = ToolRegistry()
    reg.register(_tool("calendar_create", _revienta, requires_approval=True))
    llm = _ScriptedLLM([("done", "te lo explico")])  # tras el fallo, el agente cierra honesto
    loop = _loop_con(reg, llm, tmp_path)

    # Estado: un run que paró pidiendo aprobación de calendar_create.
    run = AgentRun(task="crea un evento")
    run.messages = [
        {"role": "system", "content": "s"},
        {"role": "user", "content": "crea un evento"},
        {"role": "assistant", "content": None},
        {"role": "tool", "tool_call_id": "tcA", "content": "PENDING_APPROVAL:{}"},
    ]
    run.steps = [
        AgentStep(
            step=1,
            tool_name="calendar_create",
            tool_call_id="tcA",
            arguments={"summary": "x"},
            result="PENDING_APPROVAL:{}",
            requires_approval=True,
        )
    ]
    run.mark_pending_approval(reason="crear evento", proposed_action="...", tool_call_id="tcA")
    loop.store.save_run(run)

    out = loop.resume(run.id)

    # El fallo de la acción aprobada quedó dicho explícitamente en el historial (no re-pausa muda).
    assert any(
        "YA APROBÓ falló" in (m.get("content") or "")
        and "token caducado" in (m.get("content") or "")
        for m in out.messages
    )
    # El step aprobado refleja el error real y ya no espera aprobación.
    paso = out.steps[0]
    assert _is_error_result(paso.result) and paso.requires_approval is False
