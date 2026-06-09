"""Tests del GEPA real — optimización del prompt VALIDADA con evals de comportamiento.

Deterministas (sin LM Studio): se inyecta un stub de LLM que devuelve tool_calls conocidas, de modo
que se prueba el bucle entero (puntuar → reflexionar → re-puntuar → proponer SIN regresión) y los
guards de seguridad sobre el candidato. GEPA NUNCA escribe: solo propone un diff.
"""

from __future__ import annotations

from types import SimpleNamespace

from loombit_operator.fabrica import gepa
from loombit_operator.llm import ChatResponse, ToolCall


def _cr(tool: str | None = None, **args) -> ChatResponse:
    tcs = [ToolCall(id="tc", tool_name=tool, arguments=args)] if tool else []
    return ChatResponse(content="" if tool else "texto", tool_calls=tcs)


# ── Checkers de escenario (la verdad de tierra del eval) ───────────────────────
def test_check_redacta_correo_pasa_con_asunto_y_cuerpo():
    ok, _ = gepa._check_redacta_correo(
        _cr(
            "gmail_send",
            subject="Confirmo asistencia",
            body="Hola Ana, confirmo que iré el martes. Un saludo.",
        )
    )
    assert ok


def test_check_redacta_correo_falla_si_pregunta_asunto():
    ok, nota = gepa._check_redacta_correo(_cr("ask_user", pregunta="¿Qué asunto?"))
    assert not ok and "F1" in nota


def test_check_redacta_correo_falla_si_se_delata_como_bot():
    ok, nota = gepa._check_redacta_correo(
        _cr(
            "gmail_send",
            subject="Aviso importante",
            body="Soy un agente autónomo llamado Loombit Operator y te escribo.",
        )
    )
    assert not ok and "F4" in nota


def test_check_no_inventa_destinatario_falla_si_envia_a_ciegas():
    ok, nota = gepa._check_no_inventa_destinatario(_cr("gmail_send", to="marta@inventado.com"))
    assert not ok and "F2" in nota


def test_check_no_inventa_destinatario_pasa_si_resuelve():
    ok, _ = gepa._check_no_inventa_destinatario(_cr("contacts_find", nombre="Marta"))
    assert ok


def test_check_proactivo_brief():
    assert gepa._check_proactivo_brief(_cr("daily_brief"))[0]
    assert not gepa._check_proactivo_brief(_cr("ask_user", pregunta="¿qué quieres?"))[0]


# ── Guards sobre el candidato (la optimización no puede romper la seguridad) ───
def test_render_de_la_plantilla_real_funciona():
    from loombit_operator.agent.prompts import _BASE_PROMPT

    render = gepa._render(_BASE_PROMPT)
    assert render and "Loombit Operator" in render
    assert "{capacidades}" not in render and "{fecha_hoy}" not in render  # placeholders resueltos


def test_candidato_seguro_rechaza_si_pierde_anclajes():
    ok, motivo = gepa.candidato_es_seguro("un prompt cualquiera sin gates")
    assert not ok and "anclaje" in motivo


def test_candidato_seguro_rechaza_llaves_rotas():
    roto = "task_done gmail_send ask_user aprobar {capacidades} {fecha_hoy} {desconocido}"
    ok, motivo = gepa.candidato_es_seguro(roto)
    assert not ok


# ── Evaluación: puntúa un prompt con un stub que devuelve tool_calls ───────────
def _stub_eval(bueno: bool):
    """Stub: si `bueno`, devuelve la tool correcta por escenario; si no, pregunta (falla)."""

    def _passing(user: str) -> ChatResponse:
        u = user.lower()
        if "ana@ejemplo" in u:
            return _cr(
                "gmail_send",
                subject="Confirmo asistencia",
                body="Hola Ana, confirmo que asistiré el martes. Un saludo, Fernando.",
            )
        if "marta" in u:
            return _cr("contacts_find", nombre="Marta")
        if "centro hoy" in u:
            return _cr("daily_brief")
        if "david" in u:
            return _cr("gmail_search", query="David")
        return _cr("calendar_create", titulo="Café con Luis")

    def _chat(messages, **_kw):
        user = messages[-1]["content"]
        if bueno:
            return _passing(user)
        return _cr("read_file", path="x")  # tool inesperada en TODOS los escenarios → 0/5

    return SimpleNamespace(chat=_chat)


def test_evaluar_puntua_1_si_todo_correcto():
    score, det = gepa.evaluar("PROMPT", gepa.escenarios_por_defecto(), _stub_eval(True))
    assert score == 1.0 and all(d["ok"] for d in det)


def test_evaluar_puntua_0_si_todo_pregunta():
    score, det = gepa.evaluar("PROMPT", gepa.escenarios_por_defecto(), _stub_eval(False))
    assert score == 0.0 and not any(d["ok"] for d in det)


# ── Orquestación completa: mejora validada SIN regresión → propone diff ────────
_CANDIDATO_OK = (
    "MARKER_MEJOR — plantilla candidata válida.\n"
    "{fecha_hoy} {rol_descripcion} {dominio_ejemplos}\nCapacidades: {capacidades}\n"
    "Gates: task_done, gmail_send, ask_user, aprobar efectos externos."
)


def _stub_gepa():
    """Stub completo: el prompt BASE falla 'redacta_correo'; tras reflexión, el candidato pasa todo."""

    def _passing(user: str) -> ChatResponse:
        u = user.lower()
        if "ana@ejemplo" in u:
            return _cr(
                "gmail_send",
                subject="Confirmo asistencia",
                body="Hola Ana, confirmo que asistiré el martes. Un saludo, Fernando.",
            )
        if "marta" in u:
            return _cr("contacts_find", nombre="Marta")
        if "centro hoy" in u:
            return _cr("daily_brief")
        if "david" in u:
            return _cr("gmail_search", query="David")
        return _cr("calendar_create", titulo="Café con Luis")

    def _chat(messages, **_kw):
        sistema = messages[0]["content"]
        if "optimizador de prompts" in sistema:  # llamada de reflexión
            return ChatResponse(content=_CANDIDATO_OK)
        user = messages[-1]["content"]
        if "MARKER_MEJOR" in sistema:  # evaluando el candidato → pasa todo
            return _passing(user)
        if "ana@ejemplo" in user.lower():  # base falla solo este
            return _cr("ask_user", pregunta="¿Qué asunto le pongo?")
        return _passing(user)

    return SimpleNamespace(chat=_chat)


def test_optimizar_prompt_propone_mejora_validada_sin_regresion(monkeypatch):
    monkeypatch.setattr(gepa, "_guardar_ultimo", lambda res: None)  # no contaminar runtime/local
    res = gepa.optimizar_prompt(
        llm=_stub_gepa(), plantilla="PLANTILLA BASE original", max_intentos=1
    )
    assert res["ok"] is True
    assert res["base_score"] < res["mejor_score"]
    assert "redacta_correo" in res["fijados"]
    assert res["diff"] and "MARKER_MEJOR" in res["candidato"]


def test_optimizar_prompt_no_propone_si_no_mejora(monkeypatch):
    monkeypatch.setattr(gepa, "_guardar_ultimo", lambda res: None)  # no contaminar runtime/local

    # Stub que nunca mejora: reflexión devuelve algo inseguro → no hay candidato válido.
    def _chat(messages, **_kw):
        sistema = messages[0]["content"]
        if "optimizador de prompts" in sistema:
            return ChatResponse(content="prompt inseguro sin gates")  # lo rechaza el guard
        user = messages[-1]["content"]
        if "ana@ejemplo" in user.lower():
            return _cr("ask_user", pregunta="¿asunto?")
        return (
            _cr("daily_brief") if "centro hoy" in user.lower() else _cr("gmail_search", query="x")
        )

    res = gepa.optimizar_prompt(llm=SimpleNamespace(chat=_chat), plantilla="BASE", max_intentos=2)
    assert res["ok"] is False and res["mejor_score"] == res["base_score"]
