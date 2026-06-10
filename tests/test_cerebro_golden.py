"""
RC·Cerebro — ARNÉS golden de las piezas DETERMINISTAS del cerebro que YA existen y deben
funcionar al 100%. Cada test blinda un comportamiento real (ver docs/ALGORITMO_CEREBRO_EXISTENTE.md).
Si un cambio los rompe, el gate (scripts/verify.py) se pone ROJO. Son 100% CI (sin LM Studio).
"""

from datetime import date, datetime
from types import SimpleNamespace

import pytest

from loombit_operator import llm
from loombit_operator.agent import smalltalk
from loombit_operator.agent.contexto import ajustar_a_contexto
from loombit_operator.agent.loop import (
    AgentLoop,
    _consecutive_tool_errors,
    _describe_for_approval,
    _destinatario_claro,
    _error_brief,
    _is_error_result,
    _recipiente_resuelto,
)
from loombit_operator.agent.intencion import intencion_consecuente, tools_foco
from loombit_operator.agent.memory import AgentMemory, EntityProfile
from loombit_operator.agent.reflexion import etiquetas_de_tarea
from loombit_operator.agent.run import AgentRun, AgentStatus, AgentStep
from loombit_operator.comprension import _normalizar, _salvar_objetos
from loombit_operator.telar import _hilo_asunto, _porque_asunto, _saludo
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


# ── F3.1-3.4 · memoria operativa (titular, contactos, procedimientos) ─────────
def test_memory_owner_persiste_parcial_en_disco(tmp_path):
    p = tmp_path / "m.json"
    mem = AgentMemory(store_path=p)
    mem.set_owner(name="Fernando", company="Loombit")
    mem.set_owner(email="f@x.com")  # parcial: NO debe borrar name/company
    o = AgentMemory(store_path=p).owner  # releído de disco
    assert o["name"] == "Fernando" and o["company"] == "Loombit" and o["email"] == "f@x.com"


def test_memory_contactos_dedup_por_email_y_no_degrada_fuente(tmp_path):
    mem = AgentMemory(store_path=tmp_path / "m.json")
    mem.add_contact("Ana Pérez", "ana@acme.com", company="Acme", source="manual")
    mem.add_contact("Ana P.", "ana@acme.com", source="auto")  # mismo email → dedup
    assert len(mem.contacts) == 1
    assert mem.contacts[0].source == "manual"  # una verdad confirmada NO se degrada a 'auto'
    assert mem.find_contact("acme")  # por empresa
    assert mem.find_contact("ana@acme.com")  # por email


def test_memory_procedimientos_recupera_por_relevancia(tmp_path):
    mem = AgentMemory(store_path=tmp_path / "m.json")
    mem.add_procedure(
        "enviar correo",
        steps=["buscar contacto", "redactar", "enviar"],
        tools=["contacts_find", "gmail_send"],
    )
    p = mem.find_procedure("quiero enviar un correo a Ana")
    assert p is not None and "gmail_send" in p.tools
    assert mem.find_procedure("conciliar el banco") is None  # sin solape de palabras → None


def test_memory_to_context_block_incluye_al_titular(tmp_path):
    mem = AgentMemory(store_path=tmp_path / "m.json")
    mem.set_owner(name="Fernando")
    assert "Fernando" in mem.to_context_block()


# ── Máquina de estados del run (AgentRun): transiciones deterministas ─────────
def _step(tool="x", result="ok"):
    return AgentStep(
        step=1,
        tool_name=tool,
        tool_call_id="t",
        arguments={},
        result=result,
        requires_approval=False,
    )


def test_run_transiciones_basicas():
    r = AgentRun(task="x")
    assert r.status is AgentStatus.PENDING
    r.mark_running()
    assert r.status is AgentStatus.RUNNING
    r.mark_completed("Listo, hecho")
    assert r.status is AgentStatus.COMPLETED
    assert r.result == "Listo, hecho" and r.completed_at


def test_run_completed_sanea_codigo():
    r = AgentRun(task="x")
    r.mark_completed("for d in semana: print(d)")
    assert "print(" not in r.result  # el usuario nunca ve código


def test_run_aprobacion_y_guard_de_estado():
    r = AgentRun(task="x")
    r.mark_pending_approval("Enviar correo", "Para: a@b.com", "tc1")
    assert r.status is AgentStatus.PENDING_APPROVAL
    assert r.pending_approval["reason"] == "Enviar correo"
    r.approve()
    assert r.status is AgentStatus.RUNNING and r.pending_approval == {}
    with pytest.raises(ValueError):
        r.approve()  # ya no está en pending_approval → guard


def test_run_pregunta_y_respuesta_con_guard():
    r = AgentRun(task="x")
    r.mark_pending_question("¿ruta de las facturas?", "tc1")
    assert r.status is AgentStatus.PENDING_QUESTION
    r.answer()
    assert r.status is AgentStatus.RUNNING and r.pending_question == {}
    with pytest.raises(ValueError):
        r.answer()


def test_run_cancel_y_max_steps():
    r = AgentRun(task="x", max_steps=2)
    assert r.exceeded_max_steps is False
    r.add_step(_step())
    r.add_step(_step())
    assert r.exceeded_max_steps is True
    r.cancel()
    assert r.status is AgentStatus.CANCELLED


def test_run_roundtrip_dict_conserva_estado():
    r = AgentRun(task="reclamar cobro")
    r.mark_pending_approval("Enviar", "borrador", "tc9")
    r2 = AgentRun.from_dict(r.to_dict())
    assert r2.task == "reclamar cobro"
    assert r2.status is AgentStatus.PENDING_APPROVAL
    assert r2.pending_approval["reason"] == "Enviar"


# ── F6 · telar determinista (saludo, porqué causal, mapeo asunto→hilo) ────────
def test_telar_saludo_por_hora():
    assert _saludo(datetime(2026, 6, 9, 9, 0)) == "Buenos días"
    assert _saludo(datetime(2026, 6, 9, 15, 0)) == "Buenas tardes"
    assert _saludo(datetime(2026, 6, 9, 23, 0)) == "Buenas noches"
    assert _saludo(datetime(2026, 6, 9, 3, 0)) == "Buenas noches"


def test_telar_porque_es_causal_no_repite_detalle():
    assert "Confirmada" in _porque_asunto("reunion", "confirmada")
    assert "acción" in _porque_asunto("notificacion", "requiere_accion")
    assert _porque_asunto("reunion", "") == "Está en tu agenda."
    assert _porque_asunto("gestion", "") == "Gestión pendiente de cerrar."


def test_hilo_asunto_reunion_sin_accion_es_navigate():
    h = _hilo_asunto(
        {
            "tipo": "reunion",
            "con": "David",
            "fecha": "2026-06-11",
            "hora": "09:00",
            "estado": "confirmada",
        }
    )
    assert h["tipo"] == "reunion"
    assert "Reunión con David" in h["titulo"]
    assert "Confirmada" in h["porque"]
    assert h["accion"]["modo"] == "navigate"  # sin 'accion' → solo Ver


def test_hilo_asunto_con_accion_es_agent_task_con_gate():
    h = _hilo_asunto(
        {
            "tipo": "notificacion",
            "titulo": "Deuda no reconocida",
            "estado": "requiere_accion",
            "accion": "Verifica esta deuda",
            "origen": "Email X",
        }
    )
    assert h["accion"]["modo"] == "agent_task"
    assert h["accion"]["label"] == "Gestionar"
    assert "Verifica esta deuda" in h["accion"]["task"]
    assert "no envíes ni ejecutes nada externo" in h["accion"]["task"]  # gate en el propio task
    assert "Pide acción" in h["porque"]


# ── ALG-4.1 · relay fiel: el número de la tool == el que ve el usuario ────────
def test_relay_fiel_garantiza_las_cifras_de_la_tool():
    loop = AgentLoop(llm=SimpleNamespace())
    verbatim = "Saldo pendiente: 1500.0 €. Interés de demora: 16,27 €."
    run = SimpleNamespace(steps=[SimpleNamespace(tool_name="plan_cobro", result=verbatim)])
    out = loop._relay_fiel(
        run, "Te he calculado el cobro, son unos 1500 euros."
    )  # paráfrasis floja
    assert "16,27" in out  # la cifra EXACTA del cálculo, no la del LLM
    assert verbatim in out


def test_relay_fiel_no_duplica_si_ya_esta():
    loop = AgentLoop(llm=SimpleNamespace())
    verbatim = "Saldo pendiente: 1500.0 €."
    run = SimpleNamespace(steps=[SimpleNamespace(tool_name="plan_cobro", result=verbatim)])
    out = loop._relay_fiel(run, "Aquí tienes: " + verbatim)
    assert out.count(verbatim) == 1  # no lo repite


def test_relay_fiel_ignora_no_autoritativas_y_errores():
    loop = AgentLoop(llm=SimpleNamespace())
    run = SimpleNamespace(steps=[SimpleNamespace(tool_name="gmail_search", result="3 correos")])
    assert loop._relay_fiel(run, "narración") == "narración"  # gmail_search NO es autoritativa
    run2 = SimpleNamespace(
        steps=[SimpleNamespace(tool_name="plan_cobro", result="ERROR en 'plan_cobro': x")]
    )
    assert loop._relay_fiel(run2, "narración") == "narración"  # un error no se relaya


# ── P0 fiabilidad · intencion_consecuente: forzar la tool CORRECTA, solo con datos ──
def test_intencion_consecuente_con_datos():
    assert (
        intencion_consecuente("reclama el cobro de una factura de 800 que venció ayer") == "cobro"
    )
    assert intencion_consecuente("calcula mi 303 con ventas de 10000 al 21%") == "303"
    assert intencion_consecuente("regístrame una factura de 2000 más IVA") == "factura"
    assert intencion_consecuente("busca en mi correo los mensajes de David") == "buscar"


def test_intencion_consecuente_sin_datos_no_fuerza():
    # sin número → NO forzar (que pregunte, no que invente; regresión observada)
    assert intencion_consecuente("reclama el cobro de la factura de Acme") is None
    assert intencion_consecuente("reclámale el cobro al cliente de siempre") is None


def test_intencion_consecuente_lecturas_y_cortesias_no():
    assert intencion_consecuente("¿qué reuniones tengo esta semana?") is None
    assert intencion_consecuente("hola, ¿qué tal?") is None
    assert intencion_consecuente("hazme un resumen de hoy") is None
    assert intencion_consecuente("manda un correo a Ana") is None


def test_tools_foco_enfoca_la_tool_correcta():
    # cobro → solo plan_cobro (+ ask_user/task_done), NUNCA registrar_factura (era el bug)
    foco = tools_foco("cobro")
    assert "plan_cobro" in foco and "ask_user" in foco
    assert "registrar_factura" not in foco
    assert tools_foco(None) == set()
