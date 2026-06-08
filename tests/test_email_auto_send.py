"""
Política de envío de correo: se auto-envía si el destinatario es INEQUÍVOCO
(lo dio el usuario o contacts_find lo resolvió sin ambigüedad); si hay varios
candidatos, se confirma con tarjeta. Se prueba el discriminador `_destinatario_claro`.
"""

import json
from types import SimpleNamespace

from loombit_operator.agent.loop import AgentLoop, _destinatario_claro
from loombit_operator.llm import ToolCall


def _run(task, steps=()):
    return SimpleNamespace(task=task, steps=list(steps))


def _step(tool_name, result):
    return SimpleNamespace(tool_name=tool_name, result=result)


def test_email_que_dio_el_usuario_es_claro():
    r = _run("envía un correo a jana@x.com diciéndole que llego tarde")
    assert _destinatario_claro("jana@x.com", r) is True


def test_resuelto_sin_ambiguedad_es_claro():
    res = json.dumps({"estado": "resuelto", "mejor": {"name": "Jana", "email": "jana@x.com"}})
    r = _run("escribe a Jana", [_step("contacts_find", res)])
    assert _destinatario_claro("jana@x.com", r) is True


def test_ambiguo_no_es_claro():
    res = json.dumps({"estado": "ambiguo", "mejor": {"name": "Jana", "email": "jana@x.com"}})
    r = _run("escribe a Jana", [_step("contacts_find", res)])
    assert _destinatario_claro("jana@x.com", r) is False


def test_no_resuelto_no_es_claro():
    r = _run("escribe a Jana")
    assert _destinatario_claro("inventada@x.com", r) is False


def test_email_vacio_no_es_claro():
    assert _destinatario_claro("", _run("hola")) is False
    assert _destinatario_claro("no-es-email", _run("hola")) is False


def test_run_proactivo_nunca_auto_envia():
    # destinatario CLARO (lo da la tarea) pero proactive=True → SIEMPRE pide aprobación, no envía.
    loop = AgentLoop(llm=SimpleNamespace())
    run = SimpleNamespace(
        id="x", task="responde a jana@x.com", steps=[], messages=[], proactive=True
    )
    tc = ToolCall(
        id="tc", tool_name="gmail_send", arguments={"to": "jana@x.com", "subject": "s", "body": "b"}
    )
    out, stop = loop._execute_tool_call(tc, 1, run)
    assert stop is True and out.startswith("PENDING_APPROVAL:")
