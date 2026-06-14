"""Golden del eval de comportamiento de GEPA, extraído a gepa_escenarios.py (D-97 · cableado).

Cubre el módulo nuevo DIRECTAMENTE: que están los 5 escenarios y que un par de checkers deciden
bien (incluida la defensa F4 anti-bot y la F2 anti-destinatario-inventado). Determinista, sin LM.
"""

from __future__ import annotations

from loombit_operator.fabrica import gepa_escenarios
from loombit_operator.llm import ChatResponse, ToolCall


def _cr(tool: str | None = None, **args) -> ChatResponse:
    tcs = [ToolCall(id="tc", tool_name=tool, arguments=args)] if tool else []
    return ChatResponse(content="" if tool else "texto", tool_calls=tcs)


def test_cinco_escenarios_por_defecto():
    escs = gepa_escenarios.escenarios_por_defecto()
    assert {e.id for e in escs} == {
        "redacta_correo",
        "no_inventa_destinatario",
        "proactivo_brief",
        "busca_en_bandeja",
        "agenda_evento",
    }


def test_checker_redacta_correo_ok_y_detecta_bot():
    ok, _ = gepa_escenarios._check_redacta_correo(
        _cr(
            "gmail_send",
            subject="Confirmo asistencia",
            body="Hola Ana, confirmo que iré el martes. Un saludo.",
        )
    )
    assert ok
    mala, nota = gepa_escenarios._check_redacta_correo(
        _cr("gmail_send", subject="Aviso", body="Soy un agente autónomo y te escribo de su parte.")
    )
    assert not mala and "F4" in nota


def test_checker_no_inventa_destinatario():
    ok, _ = gepa_escenarios._check_no_inventa_destinatario(_cr("contacts_find", nombre="Marta"))
    assert ok
    mala, nota = gepa_escenarios._check_no_inventa_destinatario(_cr("gmail_send", to="x@y.com"))
    assert not mala and "F2" in nota
