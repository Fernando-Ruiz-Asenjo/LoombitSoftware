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
    _con_aviso_regulado,
    _consecutive_tool_errors,
    _corregir_fecha_calendario,
    _corregir_fecha_cobro,
    _corregir_periodo_303,
    _describe_for_approval,
    _trimestre_actual,
    _destinatario_claro,
    _error_brief,
    _filtrar_lineas_303,
    _is_error_result,
    _recipiente_resuelto,
)
from loombit_operator.agent.intencion import (
    es_lectura_agenda,
    intencion_consecuente,
    tools_excluir,
    tools_foco,
)
from loombit_operator.agent.parsers import parsear_fecha
from loombit_operator.agent.memory import AgentMemory, EntityProfile
from loombit_operator.agent.reflexion import etiquetas_de_tarea
from loombit_operator.agent.run import AgentRun, AgentStatus, AgentStep
from loombit_operator.comprension import _normalizar, _salvar_objetos
from loombit_operator.telar import (
    _hilo_asunto,
    _porque_asunto,
    _saludo,
    _urgencia_de,
    tejer_dia,
)
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


# ── DoD (no mentir): no afirmar un éxito que no ocurrió ───────────────────────
def test_relay_fiel_no_afirma_exito_si_toda_accion_material_fallo():
    loop = AgentLoop(llm=SimpleNamespace())
    run = SimpleNamespace(
        steps=[
            SimpleNamespace(
                tool_name="registrar_factura",
                result="ERROR al ejecutar 'registrar_factura': argumento inesperado 'retencion'",
            ),
            # un error DEVUELTO por la tool (no de bucle) también cuenta como fallo
            SimpleNamespace(
                tool_name="registrar_factura",
                result="ERROR al registrar la factura: falta la base imponible",
            ),
            SimpleNamespace(tool_name="task_done", result="ok"),
        ]
    )
    # el 14B narraba un éxito falso CON cifra inventada pese a que todo falló
    falso = "✅ Minuta de honorarios preparada. Total con retención IRPF del 15%: 3450 €."
    out = loop._relay_fiel(run, falso)
    assert "3450" not in out  # no propaga la cifra inventada
    assert "✅" not in out  # no presenta el éxito que no ocurrió
    assert "no he podido" in out.lower()  # honesto: no lo da por hecho


def test_relay_fiel_respeta_exito_real_no_sobre_corrige():
    loop = AgentLoop(llm=SimpleNamespace())
    verbatim = "✅ Factura F-1 registrada — emitida (a cliente). base 1000.00€ + IVA 210.00€."
    run = SimpleNamespace(steps=[SimpleNamespace(tool_name="registrar_factura", result=verbatim)])
    out = loop._relay_fiel(run, "Te he registrado la factura.")
    assert "no he podido" not in out.lower()  # NO se dispara el guard: sí hubo acción con éxito
    assert verbatim in out  # relay-fiel mantiene el resultado autoritativo real


def test_lleva_retencion_detecta_y_excluye_sin_retencion():
    from loombit_operator.skill_d_fiscal.guardas_fiscales import (
        lleva_retencion as _lleva_retencion,
    )

    # por el TEXTO de la petición
    assert _lleva_retencion("emite una minuta con retención de IRPF del 15%", {})
    assert _lleva_retencion("factura de 3000 con retencion 15%", {})
    # por el ARG explícito que pase el modelo
    assert _lleva_retencion("registra una factura de 1000", {"retencion": 15})
    assert _lleva_retencion("registra una factura", {"retención": 0.15})
    # «sin retención» NO cuenta; una factura normal tampoco; retencion=0 tampoco
    assert not _lleva_retencion("registra la factura de 1000 sin retención", {})
    assert not _lleva_retencion("registra una factura de 1000 al 21% de IVA", {})
    assert not _lleva_retencion("emite una factura a López de 5000", {"retencion": 0})


def test_es_registro_con_retencion_corta_solo_creacion():
    from loombit_operator.skill_d_fiscal.guardas_fiscales import (
        es_registro_con_retencion as _es_registro_con_retencion,
    )

    # registrar/preparar una factura o minuta CON retención → corta (rehúsa honesto, no fabrica)
    assert _es_registro_con_retencion(
        "Necesito hacer una minuta con retención de IRPF del 15%, prepárala"
    )
    assert _es_registro_con_retencion("emite una factura con retención del 15%")
    assert _es_registro_con_retencion("regístrame la minuta con retención IRPF")
    # NO corta: pregunta sin crear, factura normal, o «sin retención»
    assert not _es_registro_con_retencion("¿qué retención de IRPF me corresponde?")
    assert not _es_registro_con_retencion("registra una factura de 1000 al 21% de IVA")
    assert not _es_registro_con_retencion("emite una factura sin retención")


def test_texto_para_intencion_hereda_en_seguimiento_corto():
    from loombit_operator.agent.loop import _texto_para_intencion

    # respuesta CORTA sin intención propia («Emitida.») → hereda el último user del hilo
    run = SimpleNamespace(
        task="Emitida.",
        messages=[
            {"role": "user", "content": "Quiero registrar una factura a López de 2000 al 21%."},
            {"role": "assistant", "content": "¿Es emitida o recibida?"},
            {"role": "user", "content": "Emitida."},
        ],
    )
    txt = _texto_para_intencion(run)
    assert "2000" in txt and "factura" in txt.lower()  # heredó el contexto → ruteará a registrar
    # task con intención PROPIA → no se contamina con el historial
    run2 = SimpleNamespace(
        task="Calcula mi 303 del 2T 2026.",
        messages=[
            {"role": "user", "content": "Busca correos de David."},
            {"role": "assistant", "content": "Encontré varios."},
            {"role": "user", "content": "Calcula mi 303 del 2T 2026."},
        ],
    )
    assert _texto_para_intencion(run2) == "Calcula mi 303 del 2T 2026."
    # single-turn (sin historial previo) → devuelve el task tal cual
    run3 = SimpleNamespace(task="Emitida.", messages=[{"role": "user", "content": "Emitida."}])
    assert _texto_para_intencion(run3) == "Emitida."


def test_modelo_no_modelado_abstiene_menos_303():
    from loombit_operator.skill_d_fiscal.guardas_fiscales import (
        modelo_no_modelado as _modelo_no_modelado,
    )

    assert _modelo_no_modelado("Hazme el modelo 111 de retenciones") == "111"
    assert _modelo_no_modelado("Hazme el modelo 349 intracomunitario") == "349"
    assert _modelo_no_modelado("calcula el modelo 130 del trimestre") == "130"
    assert _modelo_no_modelado("calcula mi modelo 303 del 2T") is None  # el 303 SÍ se modela
    assert _modelo_no_modelado("¿cuánto he facturado este mes?") is None


def test_registro_guardas_aplica_dominio_fiscal():
    # D-2: las guardas de dominio fiscal viven en la skill y se aplican vía el hook blanco; el núcleo
    # no las contiene. Importar la skill las registra; el registro las aplica.
    import loombit_operator.skill_d_fiscal.guardas_fiscales  # noqa: F401  (registra las guardas)
    from loombit_operator.agent.guardas import registro_guardas

    assert registro_guardas.aplicar("emite una factura con retención del 15%")  # retención IRPF
    assert registro_guardas.aplicar("guarda el IBAN ES12 1234 de mi cliente")  # IBAN inválido
    assert registro_guardas.aplicar("hazme el modelo 111 de retenciones")  # modelo AEAT no modelado
    assert registro_guardas.aplicar("¿cuánto me deben?") is None  # nada de dominio → None


def test_relay_fiel_recoge_TODAS_las_autoritativas():
    # N facturas registradas → el usuario ve las N (antes solo salía la última)
    loop = AgentLoop(llm=SimpleNamespace())
    run = SimpleNamespace(
        steps=[
            SimpleNamespace(tool_name="registrar_factura", result="✅ Factura A — base 200€"),
            SimpleNamespace(tool_name="registrar_factura", result="✅ Factura B — base 350€"),
            SimpleNamespace(tool_name="registrar_factura", result="✅ Factura C — base 500€"),
        ]
    )
    out = loop._relay_fiel(run, "He registrado tus tres facturas.")
    assert "base 200€" in out and "base 350€" in out and "base 500€" in out  # las TRES


def test_relay_fiel_single_se_comporta_igual():
    # un solo autoritativo: se antepone su verbatim (comportamiento de siempre, sin cambios)
    loop = AgentLoop(llm=SimpleNamespace())
    run = SimpleNamespace(
        steps=[SimpleNamespace(tool_name="plan_cobro", result="Saldo pendiente: 1500 €")]
    )
    out = loop._relay_fiel(run, "Te preparo la reclamación.")
    assert out.startswith("Saldo pendiente: 1500 €") and "Te preparo la reclamación." in out


# ── P0 fiabilidad · intencion_consecuente: forzar la tool CORRECTA, solo con datos ──
def test_intencion_consecuente_con_datos():
    assert (
        intencion_consecuente("reclama el cobro de una factura de 800 que venció ayer") == "cobro"
    )
    assert intencion_consecuente("calcula mi 303 con ventas de 10000 al 21%") == "303"
    assert intencion_consecuente("regístrame una factura de 2000 más IVA") == "factura"
    assert intencion_consecuente("registra una factura emitida a López de 5000 al 21%") == "factura"
    assert intencion_consecuente("busca en mi correo los mensajes de David") == "buscar"


def test_factura_registradas_no_es_intencion_factura():
    # "facturas registradas/emitidas" = CONSULTA sobre lo ya registrado → 303, NO crear factura
    assert (
        intencion_consecuente("con las facturas registradas, calcula mi 303 del trimestre") == "303"
    )
    assert intencion_consecuente("¿cuánto IVA llevo con las 303 facturas emitidas?") == "303"


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


def test_tools_excluir_quita_las_otras_de_dominio():
    # en un cobro se EXCLUYE registrar_factura/calcular_303 (no divagar a otra tool)
    excl = tools_excluir("cobro")
    assert "registrar_factura" in excl and "calcular_303" in excl
    assert "plan_cobro" not in excl  # la propia no se excluye
    assert tools_excluir(None) == set()


def test_telar_urgencia_robusta_int_palabra_y_basura():
    assert _urgencia_de({"importancia": 3}) == 3
    assert _urgencia_de({"importancia": "alta"}) == 3
    assert _urgencia_de({"importancia": "baja"}) == 1
    assert _urgencia_de({"importancia": "2"}) == 2
    assert _urgencia_de({"importancia": "loquesea"}) == 2  # basura → defecto 2, nunca lanza
    assert _urgencia_de({}) == 2
    assert _urgencia_de({"importancia": 99}) == 3  # clamp a 1-3


def test_telar_dedup_agenda_vs_reunion_comprendida():
    # misma cita en calendario Y comprendida del correo → UN solo hilo (la reunión, más rica)
    eventos = [{"summary": "Reunión con David", "start": "2026-06-10T10:00:00Z"}]
    asuntos = [
        {
            "tipo": "reunion",
            "con": "David",
            "fecha": "2026-06-10",
            "hora": "10:00",
            "importancia": 3,
        }
    ]
    out = tejer_dia(
        now=datetime(2026, 6, 10, 8, 0),
        eventos=eventos,
        proximos=[],
        asuntos=asuntos,
        correos=[],
        inbox=[],
        vencidas=[],
        proximas=[],
        aprobaciones=0,
    )
    tipos = [h.get("tipo") for h in out["hilos"]]
    assert "reunion" in tipos  # la comprendida sí
    assert "agenda" not in tipos  # la de calendario crudo se suprimió (no duplicar)


def test_telar_agenda_se_mantiene_si_no_hay_reunion_que_la_cubra():
    # un evento de calendario SIN reunión comprendida que lo cubra → sí sale como agenda
    eventos = [{"summary": "Dentista", "start": "2026-06-10T17:00:00Z"}]
    out = tejer_dia(
        now=datetime(2026, 6, 10, 8, 0),
        eventos=eventos,
        proximos=[],
        asuntos=[],
        correos=[],
        inbox=[],
        vencidas=[],
        proximas=[],
        aprobaciones=0,
    )
    assert any(h.get("tipo") == "agenda" for h in out["hilos"])


def test_telar_no_se_cae_por_un_asunto_malformado():
    # un asunto con importancia="alta" (palabra) o un dict basura NO debe tumbar el home
    asuntos = [
        {"tipo": "reunion", "con": "David", "fecha": "2026-06-11", "importancia": "alta"},
        {"basura": True, "importancia": object()},  # provocaría error → debe omitirse, no crashear
    ]
    out = tejer_dia(
        now=datetime(2026, 6, 10, 8, 0),
        eventos=[],
        proximos=[],
        asuntos=asuntos,
        correos=[],
        inbox=[],
        vencidas=[],
        proximas=[],
        aprobaciones=0,
    )
    # el telar devolvió la tela (no lanzó) y tejió al menos el asunto válido
    assert isinstance(out.get("hilos"), list)
    assert any(h.get("tipo") == "reunion" for h in out["hilos"])


def test_corregir_fecha_calendario_proximo_lunes():
    # hoy miércoles 2026-06-10; el 14B puso sábado 13 → debe corregir a lunes 15 (mantiene la hora)
    args = {"title": "Reunión", "start_iso": "2026-06-13T10:00:00Z"}
    cambio = _corregir_fecha_calendario(
        args, "agéndame el próximo lunes a las 10", date(2026, 6, 10)
    )
    assert cambio is True
    assert args["start_iso"] == "2026-06-15T10:00:00Z"  # lunes correcto, misma hora


def test_con_aviso_regulado_fiscal_pregunta_vs_calculo():
    # pregunta de asesoramiento regulado → SIEMPRE antepone el aviso (aunque el 14B no lo dé)
    out = _con_aviso_regulado(
        "soy fisioterapeuta, ¿tengo que ponerle iva a las facturas?", "Debes aplicar IVA del 21%."
    )
    assert out.startswith("⚠️") and "gestor" in out.lower()
    assert _con_aviso_regulado("¿puedo deducir el coche?", "Sí, es deducible.").startswith("⚠️")
    # un CÁLCULO (no es asesoramiento) → NO se le mete el aviso
    calc = _con_aviso_regulado("calcula el 303 con ventas de 1000 al 21%", "IVA devengado: 210 €")
    assert calc == "IVA devengado: 210 €"
    # cobro → tampoco
    assert _con_aviso_regulado("reclama el cobro de 1500", "Saldo: 1500 €") == "Saldo: 1500 €"


def test_trimestre_actual_y_correccion_303():
    assert _trimestre_actual(date(2026, 6, 10)) == "2T 2026"  # junio = 2T
    assert _trimestre_actual(date(2026, 1, 5)) == "1T 2026"
    assert _trimestre_actual(date(2026, 11, 1)) == "4T 2026"
    # sin trimestre en la petición → usa el actual (no la adivinanza del 14B)
    a = {"periodo": "Primer trimestre"}
    assert _corregir_periodo_303(a, "calcula el 303 con ventas de 1000 al 21%", date(2026, 6, 10))
    assert a["periodo"] == "2T 2026"
    # si el usuario LO indica → se respeta (no se toca)
    b = {"periodo": "1T 2026"}
    assert _corregir_periodo_303(b, "calcula el 303 del 1T 2026", date(2026, 6, 10)) is False


def test_parsear_fecha_hace_n_semanas_y_dias():
    hoy = date(2026, 6, 10)
    assert parsear_fecha("venció hace tres semanas", hoy) == date(2026, 5, 20)  # 21 días exactos
    assert parsear_fecha("hace 10 días", hoy) == date(2026, 5, 31)
    assert parsear_fecha("hace una semana", hoy) == date(2026, 6, 3)


def test_parsear_fecha_hace_n_meses_calendario():
    assert parsear_fecha("venció hace un mes", date(2026, 6, 10)) == date(2026, 5, 10)
    assert parsear_fecha("hace dos meses", date(2026, 6, 10)) == date(2026, 4, 10)
    assert parsear_fecha("hace 7 meses", date(2026, 6, 10)) == date(2025, 11, 10)  # cruza el año
    # clamp del día: 31 de marzo - 1 mes = 28 feb (no existe 31 feb)
    assert parsear_fecha("hace un mes", date(2026, 3, 31)) == date(2026, 2, 28)


def test_corregir_fecha_cobro_vencimiento_relativo():
    # el 14B puso 2026-05-17 (24 días); 'hace tres semanas' desde el 10/6 = 2026-05-20 (21)
    args = {"total": 1000, "fecha_vencimiento": "2026-05-17"}
    cambio = _corregir_fecha_cobro(
        args, "reclama el cobro, venció hace tres semanas", date(2026, 6, 10)
    )
    assert cambio is True and args["fecha_vencimiento"] == "2026-05-20"


def test_corregir_fecha_calendario_no_toca_si_ya_correcta_o_sin_relativa():
    # 14B ya correcto ('mañana' = jueves 11 desde miércoles 10) → no cambia
    a1 = {"start_iso": "2026-06-11T09:00:00Z"}
    assert _corregir_fecha_calendario(a1, "agéndame mañana a las 9", date(2026, 6, 10)) is False
    # sin marcador relativo (fecha explícita) → no toca
    a2 = {"start_iso": "2026-06-20T12:00:00Z"}
    assert (
        _corregir_fecha_calendario(a2, "agéndame el 20 de junio a las 12", date(2026, 6, 10))
        is False
    )


def test_filtrar_lineas_303_quita_inventadas():
    # el usuario dio ventas 10000@21 y compras 2000@21; el 14B añadió "servicios 5000@10"
    args = {
        "iva_repercutido": [
            {"base": 10000, "tipo": 0.21},
            {"base": 5000, "tipo": 0.10},  # INVENTADA (5000 no está en el mensaje)
        ],
        "iva_soportado": [{"base": 2000, "tipo": 0.21}],
    }
    task = "Calcula el 303 con ventas de 10000 al 21% y compras de 2000 al 21%."
    out, quitadas = _filtrar_lineas_303(args, task)
    assert quitadas == 1
    assert out["iva_repercutido"] == [{"base": 10000, "tipo": 0.21}]
    assert out["iva_soportado"] == [{"base": 2000, "tipo": 0.21}]


def test_filtrar_lineas_303_no_toca_si_no_hay_cifras():
    # números en palabras → no filtra (evita falsos positivos)
    args = {"iva_repercutido": [{"base": 1000, "tipo": 0.21}]}
    out, quitadas = _filtrar_lineas_303(args, "calcula el 303 con ventas de mil al 21%")
    assert quitadas == 0 and out["iva_repercutido"] == [{"base": 1000, "tipo": 0.21}]


def test_intencion_cobros_pendientes_fuerza_la_tool():
    from loombit_operator.agent.intencion import intencion_consecuente, tools_foco

    assert intencion_consecuente("¿cuánto me deben en total?") == "cobros_pend"
    assert intencion_consecuente("¿quién me debe dinero?") == "cobros_pend"
    assert intencion_consecuente("enséñame mis cobros pendientes") == "cobros_pend"
    # NO confundir con reclamar UN cobro (plan_cobro) ni con facturación
    assert intencion_consecuente("reclama el cobro de 1500€ vencido el 1 de mayo") == "cobro"
    assert tools_foco("cobros_pend") == {"cobros_pendientes"}


def test_intencion_facturacion_fuerza_resumen():
    from loombit_operator.agent.intencion import intencion_consecuente, tools_foco

    assert intencion_consecuente("¿cuánto he facturado este mes?") == "facturacion"
    assert intencion_consecuente("cuánto he ingresado en junio") == "facturacion"
    assert intencion_consecuente("enséñame mi facturación de 2026") == "facturacion"
    # NO confundir con registrar una factura ni con cobros
    assert intencion_consecuente("regístrame una factura de 1000€ al 21%") == "factura"
    assert intencion_consecuente("¿cuánto me han pagado?") != "facturacion"
    assert tools_foco("facturacion") == {"resumen_facturacion"}  # SIN task_done: fuerza sumar


def test_intencion_resumen_financiero_global_y_compuesta():
    from loombit_operator.agent.intencion import (
        intencion_consecuente,
        tools_excluir,
        tools_foco,
    )

    # COMPUESTA (≥2 métricas coordinadas) → resumen_financiero (antes solo respondía la 1ª)
    assert intencion_consecuente("¿cuánto he facturado y cuánto me deben?") == "resumen_financiero"
    assert (
        intencion_consecuente("¿cuánto facturé y cuánto IVA debo pagar este trimestre?")
        == "resumen_financiero"
    )
    # GLOBAL ('resumen financiero', 'cómo va mi negocio')
    assert intencion_consecuente("dame un resumen financiero del trimestre") == "resumen_financiero"
    assert intencion_consecuente("¿cómo va mi negocio este mes?") == "resumen_financiero"
    # NO rompe las single-métrica: cada una sigue a SU tool específica
    assert intencion_consecuente("¿cuánto he facturado este mes?") == "facturacion"
    assert intencion_consecuente("¿cuánto me deben en total?") == "cobros_pend"
    assert (
        intencion_consecuente("con las facturas registradas, calcula mi 303 del trimestre") == "303"
    )
    # anti-falso-positivo: 'cuánto IVA he facturado' es UNA métrica (iva como objeto), no compuesta
    assert intencion_consecuente("¿cuánto IVA he facturado?") != "resumen_financiero"
    # anti-falso-positivo: '¿cómo voy a pagar esto?' NO es un resumen financiero
    assert intencion_consecuente("¿cómo voy a pagar esto?") != "resumen_financiero"
    # foco: una sola tool que COMPONE; excluye del run las demás dominio-tools
    assert tools_foco("resumen_financiero") == {"resumen_financiero"}
    excl = tools_excluir("resumen_financiero")
    assert "resumen_financiero" not in excl
    assert "resumen_facturacion" in excl and "cobros_pendientes" in excl


def test_rango_periodo_soporta_mes_y_trimestre():
    from datetime import date

    from loombit_operator.skill_d_fiscal.intake import rango_periodo

    assert rango_periodo("junio 2026")[:2] == (date(2026, 6, 1), date(2026, 6, 30))
    assert rango_periodo("este mes", date(2026, 6, 10))[:2] == (date(2026, 6, 1), date(2026, 6, 30))
    assert rango_periodo("2T 2026")[:2] == (date(2026, 4, 1), date(2026, 6, 30))  # delega trimestre
    assert rango_periodo("febrero 2025")[:2] == (date(2025, 2, 1), date(2025, 2, 28))
    assert rango_periodo("")[0] is None  # sin periodo → no acota


def test_intencion_recordatorio_fuerza_calendario_sin_preguntar():
    from loombit_operator.agent.intencion import intencion_consecuente, tools_foco

    assert (
        intencion_consecuente("recuérdame pagar 1.200€ al proveedor el viernes") == "recordatorio"
    )
    assert intencion_consecuente("recuérdame llamar a Ana mañana") == "recordatorio"
    # 'apúntame que [hecho]' es AMBIGUO (nota/preferencia sin fecha) → NO se fuerza a calendario
    assert intencion_consecuente("apúntame que el cliente prefiere transferencia") != "recordatorio"
    # 'apúntame [3 facturas]' sigue siendo factura, no recordatorio
    assert intencion_consecuente("apúntame 3 facturas recibidas de 200€ al 21%") == "factura"
    # el foco de recordatorio es SOLO calendar_create (sin ask_user ni task_done): que lo CREE, no
    # pueda escaparse a preguntar el NIF. calendar_create gatea → el usuario lo aprueba.
    assert tools_foco("recordatorio") == {"calendar_create"}
    assert "ask_user" not in tools_foco("recordatorio")


def test_rango_trimestre_acota_el_303():
    from datetime import date

    from loombit_operator.skill_d_fiscal.intake import rango_trimestre

    assert rango_trimestre("2T 2026") == (date(2026, 4, 1), date(2026, 6, 30), "2T 2026")
    assert rango_trimestre("1T 2026") == (date(2026, 1, 1), date(2026, 3, 31), "1T 2026")
    assert rango_trimestre("primer trimestre 2026")[:2] == (date(2026, 1, 1), date(2026, 3, 31))
    assert rango_trimestre("4T 2025") == (date(2025, 10, 1), date(2025, 12, 31), "4T 2025")
    # sin trimestre claro → no filtra (None) para que el llamante avise, no sume mal en silencio
    assert rango_trimestre("")[0] is None
    assert rango_trimestre("mi iva")[0] is None


def test_es_factura_emitida_reconoce_terminos_fiscales():
    from loombit_operator.tools.dominio import _es_factura_emitida

    # EMITIDA (IVA repercutido/devengado, ventas) — el bug era que 'repercutido' caía a recibida
    assert _es_factura_emitida("repercutido") is True
    assert _es_factura_emitida("devengado") is True
    assert _es_factura_emitida("emitida") is True
    assert _es_factura_emitida("venta") is True
    # RECIBIDA (soportado, compras)
    assert _es_factura_emitida("soportado") is False
    assert _es_factura_emitida("recibida") is False
    assert _es_factura_emitida("compra") is False
    # sentido ambiguo → infiere de la contraparte (no invertir el 303 en silencio)
    assert _es_factura_emitida("", "Cliente Acme SL") is True
    assert _es_factura_emitida("xyz", "Proveedor Beta") is False


def test_fmt_evento_con_fecha_pone_el_dia_correcto():
    from loombit_operator.tools.brief import _fmt_evento

    ev = {"start": "2026-06-11T09:00:00+02:00", "summary": "Reunión con David"}
    # 2026-06-11 es JUEVES → el código lo pone (el 14B no tiene que adivinar)
    assert _fmt_evento(ev, con_fecha=True) == "Jueves 11/06 · 09:00 Reunión con David"
    assert _fmt_evento(ev) == "09:00 Reunión con David"  # sin fecha (vista de hoy), igual que antes


def test_calendar_semana_registrada_y_ruteada():
    from loombit_operator.tools import tool_registry
    from loombit_operator.tools.registry import select_tool_names

    assert tool_registry.get("calendar_semana").category == "connector"  # existe
    # '¿qué reuniones tengo esta semana?' → debe ofrecer la tool de semana (antes solo había hoy)
    assert "calendar_semana" in select_tool_names("¿qué reuniones tengo esta semana?")
    assert "calendar_semana" in select_tool_names("enséñame mi agenda de los próximos días")
    # 'cierre de mes' debe ofrecer daily_brief (que agrega cobros vencidos + aprobaciones)
    assert "daily_brief" in select_tool_names("prepárame el cierre de mes")


def test_es_lectura_agenda():
    # preguntas de agenda = lectura (no crear evento)
    assert es_lectura_agenda("¿qué reuniones tengo esta semana?") is True
    assert es_lectura_agenda("¿tengo alguna cita el jueves?") is True
    assert es_lectura_agenda("agéndame una reunión con Marta el martes") is False  # crear, no leer
    assert es_lectura_agenda("hola") is False
