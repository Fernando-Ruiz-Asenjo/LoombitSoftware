"""
RC·Cerebro — ARNÉS golden de las piezas DETERMINISTAS del cerebro que YA existen y deben
funcionar al 100%. Cada test blinda un comportamiento real (ver docs/ALGORITMO_CEREBRO_EXISTENTE.md).
Si un cambio los rompe, el gate (scripts/verify.py) se pone ROJO. Son 100% CI (sin LM Studio).
"""

from datetime import date
from types import SimpleNamespace

from loombit_operator import llm
from loombit_operator.agent import smalltalk
from loombit_operator.agent.contexto import ajustar_a_contexto
from loombit_operator.agent.loop import (
    _consecutive_tool_errors,
    _describe_for_approval,
    _destinatario_claro,
    _error_brief,
    _is_error_result,
    _recipiente_resuelto,
)
from loombit_operator.agent.memory import EntityProfile
from loombit_operator.agent.reflexion import etiquetas_de_tarea
from loombit_operator.comprension import _normalizar, _salvar_objetos
from loombit_operator.tool_labels import (
    capability_block,
    humanize_user_text,
    looks_like_code,
    safe_user_result,
)


# ── F2.1 · smalltalk (fricción cero) ─────────────────────────────────────────
def test_smalltalk_cortesias_responden_al_instante():
    assert smalltalk.respuesta_social("hola") == smalltalk._R_SALUDO
    assert smalltalk.respuesta_social("buenas tardes") == smalltalk._R_SALUDO
    assert smalltalk.respuesta_social("gracias") == smalltalk._R_GRACIAS
    assert smalltalk.respuesta_social("vale") == smalltalk._R_OK
    assert smalltalk.respuesta_social("adios") == smalltalk._R_DESPEDIDA


def test_smalltalk_no_intercepta_tareas_reales():
    # Una cifra, un '@' o frase larga = intención real → None (lo lleva el agente).
    assert smalltalk.respuesta_social("reclama el cobro de 1500 euros") is None
    assert smalltalk.respuesta_social("envíame el informe a ana@x.com") is None
    assert smalltalk.respuesta_social("hola, mándame el informe del trimestre a Ana") is None


# ── F4.2 · etiquetas_de_tarea (indexar lecciones) ────────────────────────────
def test_etiquetas_de_tarea_extrae_tokens_significativos():
    assert etiquetas_de_tarea("reclamar el cobro de una factura vencida") == [
        "cobro",
        "factura",
        "reclamar",
        "vencida",
    ]


# ── F5.3 · parser tolerante de comprensión (no perderlo TODO si el JSON viene truncado) ──
def test_salvar_objetos_recupera_aunque_el_array_venga_truncado():
    # El 14B corta a max_tokens: el último objeto queda a medias → no debe perderse el resto.
    truncado = '[{"a": 1}, {"b": 2}, {"c":'
    assert _salvar_objetos(truncado) == [{"a": 1}, {"b": 2}]


def test_salvar_objetos_array_valido_y_con_texto_alrededor():
    assert _salvar_objetos('[{"x": 1}]') == [{"x": 1}]
    assert _salvar_objetos('aquí van: [{"k": "v"}] fin') == [{"k": "v"}]


def test_salvar_objetos_respeta_objetos_anidados():
    assert _salvar_objetos('[{"a": {"b": 1}}]') == [{"a": {"b": 1}}]


# ── F8 · saneadores del texto que VE el usuario ──────────────────────────────
def test_humanize_quita_nombres_de_tool():
    out = humanize_user_text("Lo busqué usando gmail_search y encontré 3 correos")
    assert "gmail_search" not in out


def test_looks_like_code_detecta_codigo():
    assert looks_like_code("for d in dias: print(d)") is True
    assert looks_like_code("Tienes 3 reuniones hoy.") is False


def test_safe_user_result_sustituye_codigo_por_mensaje_honesto():
    churro = "for d in semana: print(d.strftime('%A'))"
    assert safe_user_result(churro) != churro  # no se le enseña código al usuario
    limpio = "Listo, te he enviado el correo."
    assert safe_user_result(limpio) == limpio


# ── ALG-0.2 · reintento ante errores TRANSITORIOS (no ante 400 determinista) ──
class _FakeResp:
    def __init__(self, status: int) -> None:
        self.status_code = status

    def json(self) -> dict:
        return {"choices": [{"message": {"content": "ok"}}]}


class _FakeClient:
    def __init__(self, statuses: list[int]) -> None:
        self._statuses = list(statuses)
        self.calls = 0

    def post(self, url: str, json: dict | None = None) -> _FakeResp:  # noqa: A002
        s = self._statuses[self.calls]
        self.calls += 1
        return _FakeResp(s)


def test_reintenta_ante_503_y_devuelve_el_200(monkeypatch):
    monkeypatch.setattr(llm, "_BACKOFF_BASE", 0)
    c = _FakeClient([503, 200])
    r = llm._post_con_reintento(c, "http://x/chat", {})
    assert r.status_code == 200
    assert c.calls == 2  # reintentó una vez


def test_no_reintenta_ante_400_determinista(monkeypatch):
    monkeypatch.setattr(llm, "_BACKOFF_BASE", 0)
    c = _FakeClient([400, 200])
    r = llm._post_con_reintento(c, "http://x/chat", {})
    assert r.status_code == 400
    assert c.calls == 1  # un 400 (contexto/esquema) NO se reintenta


def test_agota_reintentos_y_devuelve_el_ultimo(monkeypatch):
    monkeypatch.setattr(llm, "_BACKOFF_BASE", 0)
    c = _FakeClient([503, 503, 503])
    r = llm._post_con_reintento(c, "http://x/chat", {})
    assert r.status_code == 503
    assert c.calls == 3  # tope de intentos


# ── ALG-0.1 · asegurar_contexto (evita el 400 por desbordar el contexto) ──────
def test_contexto_no_recorta_si_cabe():
    m = [{"role": "system", "content": "sys"}, {"role": "user", "content": "hola"}]
    t = [{"a": 1}]
    mm, tt, rec = ajustar_a_contexto(m, t, n_ctx=8192, max_tokens=1024)
    assert rec is False and mm == m and tt == t


def test_contexto_recorta_historial_conservando_system_y_ultimo():
    grande = "x" * 4000
    m = [{"role": "system", "content": "sys"}] + [
        {"role": "user", "content": grande} for _ in range(10)
    ]
    mm, tt, rec = ajustar_a_contexto(m, [{"a": 1}], n_ctx=2000, max_tokens=512)
    assert rec is True
    assert len(mm) < len(m)
    assert mm[0]["content"] == "sys"  # nunca toca el system


def test_contexto_recorta_tools_como_ultimo_recurso():
    m = [{"role": "system", "content": "x" * 5000}, {"role": "user", "content": "hola"}]
    t = [{"n": i, "d": "y" * 300} for i in range(20)]
    mm, tt, rec = ajustar_a_contexto(m, t, n_ctx=2000, max_tokens=512, min_tools=4)
    assert rec is True and 4 <= len(tt) < 20


# ── F1.8 · _describe_for_approval (borrador real en la tarjeta de aprobación) ──
def test_describe_calendar_lee_title_no_summary():
    reason, prop = _describe_for_approval(
        "calendar_create",
        {"title": "Reunión con David", "start_iso": "2026-06-14T10:00:00Z", "duration_minutes": 30},
    )
    assert "evento" in reason.lower()
    assert "Reunión con David" in prop  # antes salía vacío (leía 'summary')
    assert "30" in prop


def test_describe_gmail_muestra_destinatario_y_asunto():
    reason, prop = _describe_for_approval(
        "gmail_send", {"to": "a@b.com", "subject": "Hola", "body": "Texto del correo"}
    )
    assert "a@b.com" in prop and "Hola" in prop and "Texto del correo" in prop


# ── F1.7 · guardia anti-email-inventado (seguridad de envío, D-20) ────────────
def _fake_run(task="", steps=None, messages=None):
    def _paso(tool_name="", result="", **_):
        return SimpleNamespace(tool_name=tool_name, result=result)

    return SimpleNamespace(
        task=task,
        steps=[_paso(**s) for s in (steps or [])],
        messages=messages or [],
    )


def test_recipiente_acepta_email_de_la_peticion():
    run = _fake_run(task="envía un correo a juan@x.com con el informe")
    assert _recipiente_resuelto("juan@x.com", run) is True


def test_recipiente_rechaza_email_inventado():
    # el modelo se saca un email que NO está ni en la petición ni en contacts_find → fail-closed
    run = _fake_run(task="envía un correo a David", steps=[])
    assert _recipiente_resuelto("inventado@x.com", run) is False


def test_recipiente_acepta_email_resuelto_por_contacts_find():
    run = _fake_run(
        task="escribe a Ana",
        steps=[{"tool_name": "contacts_find", "result": 'mejor: "ana@x.com"'}],
    )
    assert _recipiente_resuelto("ana@x.com", run) is True


def test_recipiente_rechaza_lo_que_no_es_email():
    assert _recipiente_resuelto("David", _fake_run(task="a David")) is False


def test_destinatario_claro_si_lo_escribio_el_usuario():
    run = _fake_run(task="manda un correo a juan@x.com")
    assert _destinatario_claro("juan@x.com", run) is True
    run2 = _fake_run(task="manda un correo a David", steps=[], messages=[])
    assert _destinatario_claro("otro@x.com", run2) is False


# ── F8.3 · capability_block no filtra nombres técnicos de tool ────────────────
def test_capability_block_en_humano_sin_jerga():
    bloque = capability_block()
    for tecnico in ("gmail_send", "calendar_create", "contacts_find", "memory_search"):
        assert tecnico not in bloque
    assert "Enviar correos" in bloque  # sí, en humano


# ── F5 · _normalizar: cognición fiable (guards deterministas de alto riesgo) ──
_HOY = date(2026, 6, 9)


def test_normalizar_deuda_no_reconocida_siempre_importante_y_requiere_accion():
    # El caso de MÁS riesgo no se deja al azar del LLM: deuda/fraude → imp 3 + requiere_accion.
    out = _normalizar(
        {
            "titulo": "Deuda no reconocida de Abogados CEA",
            "tipo": "notificacion",
            "estado": "informativa",  # el LLM la marcó floja → el guard la corrige
            "fecha": "2026-12-31",
        },
        _HOY,
    )
    assert out is not None
    assert out["importancia"] == 3
    assert out["estado"] == "requiere_accion"
    assert out["accion"]  # propone verificar, no pagar a ciegas


def test_normalizar_ruido_de_marketing_no_pide_accion():
    out = _normalizar(
        {
            "titulo": "Informe de rendimiento mensual",
            "tipo": "notificacion",
            "estado": "requiere_accion",
        },
        _HOY,
    )
    assert out is not None
    assert out["estado"] == "informativa"
    assert out["importancia"] == 1


def test_normalizar_hora_y_descarta_lo_pasado_o_sin_ancla():
    out = _normalizar(
        {
            "titulo": "Reunión",
            "tipo": "reunion",
            "estado": "confirmada",
            "hora": "900",
            "fecha": "2026-12-31",
        },
        _HOY,
    )
    assert out["hora"] == "09:00"
    assert _normalizar({}, _HOY) is None  # sin título ni origen → no se afirma
    assert _normalizar({"titulo": "X", "fecha": "2020-01-01"}, _HOY) is None  # cosa pasada → fuera


# ── F3.5 · EntityProfile: perfil de pagador (alimenta cobros y antifraude) ────
def test_entity_profile_pays_late():
    moroso = EntityProfile("Cliente A", payments=[10, 20, 30])
    assert moroso.avg_days_late == 20.0
    assert moroso.late_count == 3
    assert moroso.pays_late is True

    puntual = EntityProfile("Cliente B", payments=[1, -2, 0])
    assert puntual.pays_late is False  # media <= 5

    sin_datos = EntityProfile("Cliente C")
    assert sin_datos.avg_days_late == 0.0
    assert sin_datos.pays_late is False  # sin pagos no se afirma morosidad


# ── F1.9 / F1.6 · anti-bucle del motor (detectar errores y flailing) ──────────
def test_is_error_result_solo_marca_errores_del_bucle():
    assert _is_error_result("ERROR en 'gmail_send': boom") is True
    assert _is_error_result("ERROR: argumentos invalidos para 'x'") is True
    assert _is_error_result("Listo, te lo he enviado.") is False
    assert _is_error_result("ERROR: algo no listado en prefijos") is False


def test_error_brief_una_linea_y_recorta():
    assert _error_brief("primera línea\nsegunda línea") == "primera línea"
    largo = "x" * 200
    assert _error_brief(largo).endswith("…") and len(_error_brief(largo)) <= 161


def test_consecutive_tool_errors_cuenta_seguidos_e_ignora_otras_tools():
    run = _fake_run(
        steps=[
            {"tool_name": "gmail_search", "result": "ok"},
            {"tool_name": "calendar_create", "result": "creado"},
            {"tool_name": "gmail_search", "result": "ERROR en 'gmail_search': a"},
            {"tool_name": "gmail_search", "result": "ERROR en 'gmail_search': b"},
        ]
    )
    assert _consecutive_tool_errors(run, "gmail_search") == 2  # los 2 del final, el "ok" corta
