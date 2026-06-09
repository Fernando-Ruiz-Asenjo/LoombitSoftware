"""
RC·Cerebro — ARNÉS golden de las piezas DETERMINISTAS del cerebro que YA existen y deben
funcionar al 100%. Cada test blinda un comportamiento real (ver docs/ALGORITMO_CEREBRO_EXISTENTE.md).
Si un cambio los rompe, el gate (scripts/verify.py) se pone ROJO. Son 100% CI (sin LM Studio).
"""

from loombit_operator import llm
from loombit_operator.agent import smalltalk
from loombit_operator.agent.contexto import ajustar_a_contexto
from loombit_operator.agent.loop import _describe_for_approval
from loombit_operator.agent.reflexion import etiquetas_de_tarea
from loombit_operator.comprension import _salvar_objetos
from loombit_operator.tool_labels import humanize_user_text, looks_like_code, safe_user_result


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
