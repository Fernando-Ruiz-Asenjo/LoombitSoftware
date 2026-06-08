"""El agente NUNCA pregunta el asunto/cuerpo de un correo: los redacta él.

Barrera de código en AgentLoop._execute_tool_call: si el modelo llama a ask_user
preguntando por el asunto o el cuerpo, se intercepta (no se pausa al usuario) y se le
ordena redactarlo. Regresión del caso real: "para mandar un correo me pregunto 2 veces".
"""

from types import SimpleNamespace

from loombit_operator.agent.loop import AgentLoop
from loombit_operator.llm import ToolCall


def _tc(question: str) -> ToolCall:
    return ToolCall(id="tc1", tool_name="ask_user", arguments={"question": question})


def test_pregunta_por_el_asunto_se_intercepta_y_no_pausa():
    loop = AgentLoop(llm=SimpleNamespace())  # el LLM no se usa en _execute_tool_call
    run = SimpleNamespace(id="r1")
    result, needs_stop = loop._execute_tool_call(_tc("¿Cuál es el asunto del correo?"), 1, run)
    assert needs_stop is False  # no molesta al usuario
    assert "asunto" in result.lower() and "redác" in result.lower()


def test_pregunta_por_el_cuerpo_se_intercepta():
    loop = AgentLoop(llm=SimpleNamespace())
    run = SimpleNamespace(id="r1")
    result, needs_stop = loop._execute_tool_call(_tc("Dime qué pongo en el body del email"), 1, run)
    assert needs_stop is False


def test_pregunta_legitima_si_pausa():
    """Un dato imposible de deducir (un email desconocido) SÍ se pregunta al usuario."""
    loop = AgentLoop(llm=SimpleNamespace())
    run = SimpleNamespace(id="r1")
    result, needs_stop = loop._execute_tool_call(_tc("¿Cuál es el email de Jana?"), 1, run)
    assert needs_stop is True
    assert result.startswith("PENDING_QUESTION:")
