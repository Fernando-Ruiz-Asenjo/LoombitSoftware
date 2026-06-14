"""
motor_loop.py — el cuerpo del bucle ReAct del agente (antes `AgentLoop._execute`).

Extraído de loop.py (en deuda de tamaño, >400; ratchet de la Brújula) SIN cambiar la lógica: las
funciones reciben la instancia `loop` como primer argumento y acceden a `loop.llm/registry/store`; los
métodos de `AgentLoop` quedan como wrappers finos que delegan aquí. Llama a los demás métodos vía la
instancia (`loop._execute_tool_call`, etc.) → no importa `motor_tools` (sin ciclo). Importa de los
módulos hoja (`salida`, `seguridad`) y de los colaboradores del agente, nunca de `loop`.
"""

from __future__ import annotations

import logging

from ..config import get_settings
from ..llm import ChatResponse, tool_result_message
from .contexto import ajustar_a_contexto
from .descomposicion import MENU, clasificar_intencion, merece_clasificar, resolver
from .guardas import registro_guardas
from .intencion import (
    es_lectura_agenda,
    intencion_consecuente,
    tiene_dato,
    tools_excluir,
    tools_foco,
)
from . import memory
from .prompts import build_system_prompt
from .run import AgentRun, AgentStatus, AgentStep
from .salida import (
    _SENTINEL_APPROVAL,
    _SENTINEL_DONE,
    _SENTINEL_QUESTION,
    _extract_sentinel,
    _first_sentinel,
    _inject_loop_hint,
    _log_conversation_event,
    _parse_approval_json,
    _strip_tool_artifacts,
    _update_memory,
)
from .seguridad import _blindar_tool_results

logger = logging.getLogger(__name__)


def _texto_para_intencion(run: AgentRun) -> str:
    """Texto sobre el que clasificar la intención (force-tool). Si el ÚLTIMO mensaje no tiene intención
    propia y es CORTO (una respuesta de seguimiento: «Emitida.», «¿y en junio?»), hereda el último
    mensaje del usuario del hilo —donde vive el dato/intención—. Así un seguimiento terso rutea bien y
    el 14B no fabrica un «✅ hecho» sin llamar la tool. Si el task ya tiene intención clara, se respeta
    (no se contamina con el historial)."""
    task = run.task or ""
    if len(task.split()) > 6 or intencion_consecuente(task) is not None:
        return task
    for m in reversed(run.messages or []):
        if m.get("role") == "user" and (m.get("content") or "") != task:
            return ((m.get("content") or "") + " " + task).strip()
    return task


def ejecutar(loop, run: AgentRun) -> AgentRun:
    run.mark_running()
    loop.store.save_run(run)

    # Primer mensaje si es un run nuevo (sin historial). SIEMPRE con la memoria (dueño +
    # lecciones): sin ella el modelo se inventa la identidad (firmó "José Martínez" en vez de
    # Fernando). El dueño/firma es contexto, no se deja al azar.
    if not run.messages:
        memory_block = memory.get_memory().to_context_block(task_hint=run.task)
        run.messages = [
            {"role": "system", "content": build_system_prompt(run.profile, memory_block)},
            {"role": "user", "content": run.task},
        ]

    # Guardas de DOMINIO pre-intent (D-2): el dominio (skill_d_fiscal) registra abstenciones
    # honestas para lo que Loombit NO modela (retención IRPF, IBAN inválido, modelos AEAT). El
    # núcleo BLANCO solo consulta el hook; no sabe de fiscalidad. Si una guarda aplica, corta
    # ANTES del ReAct (evita que el 14B fabrique un «✅ hecho» con cifras erróneas).
    _guarda_msg = registro_guardas.aplicar(run.task)
    if _guarda_msg:
        logger.info("guarda de dominio aplicó → abstención honesta run=%s", run.id)
        run.mark_completed(_guarda_msg)
        _log_conversation_event(run, "completed", run.result)
        loop.store.save_run(run)
        return run

    try:
        tools_schema = loop.registry.to_openai(profile=run.profile, task=run.task)
        # P0 fiabilidad: en intenciones consecuentes (cobro/303/factura/buscar) el 14B a veces
        # calcula/contesta a ojo (fabrica) o llama a la tool equivocada. En el PRIMER paso forzamos
        # la tool Y la enfocamos a la correcta. Solo si la petición trae datos (si no, que pregunte).
        # ROUTING (D-1): el regex es el FAST-PATH barato; si NO casa pero la petición tiene señal
        # de dominio, un clasificador LLM cubre la cola larga (fin del whack-a-mole: no hay que
        # añadir un regex por cada fraseo nuevo). En conversación, una respuesta corta hereda la
        # intención del turno anterior (_texto_para_intencion) → «Emitida.» fuerza registrar_factura.
        _texto_rt = _texto_para_intencion(run)
        _intencion = intencion_consecuente(_texto_rt)
        if _intencion is None and merece_clasificar(_texto_rt):
            _cand = clasificar_intencion(_texto_rt, loop.llm)
            # cobro/303/factura SIN dato no se fuerzan (que pregunte, no que invente un importe).
            if _cand and not (_cand in ("cobro", "303", "factura") and not tiene_dato(_texto_rt)):
                _intencion = _cand
                logger.info(
                    "intención por clasificador LLM (regex no casó): %s run=%s", _cand, run.id
                )
        # A1 (gate de ambigüedad INTERNO): si la petición cruza varias intenciones de LECTURA
        # (cross-domain, p.ej. financiero + agenda), se descompone, se ejecuta cada métrica con su
        # tool determinista y se compone UNA respuesta aquí — sin preguntar al usuario. Si no
        # aplica (mono-intención), sigue el flujo single-intent de abajo (0 regresión).
        if loop._intentar_multi_intent(run):
            return run
        # Exclusiones para TODO el run: otras tools de dominio + (si es pregunta de agenda)
        # calendar_create, para que una LECTURA no acabe creando un evento.
        _excl_run = tools_excluir(_intencion)
        if es_lectura_agenda(run.task):
            _excl_run = _excl_run | {"calendar_create"}
        while True:
            # Guard: cancelación externa (el usuario pulsó "Detener")
            fresh = loop.store.get(run.id)
            if fresh.status == AgentStatus.CANCELLED:
                return fresh

            # Guard: límite de pasos
            if run.exceeded_max_steps:
                run.mark_failed(
                    f"Límite de {run.max_steps} pasos alcanzado sin completar la tarea."
                )
                loop._aprender_de_fallo(run)
                loop.store.save_run(run)
                return run

            # ── Llamar al LLM ──────────────────────────────────────────────
            logger.debug(
                "AgentLoop step=%d run=%s messages=%d",
                run.step_count,
                run.id,
                len(run.messages),
            )
            # ALG-0.1: enfocar/excluir las tools ANTES de recortar por contexto. Si se recorta
            # primero y se enfoca después, el recorte (que corta la lista ordenada por la cola)
            # puede tirar justo la tool enfocada y task_done cuando la petición activa muchos
            # grupos — la compuesta «facturado + me-deben» inflaba a ~20 tools y el recorte dejaba
            # 10 SIN resumen_financiero → el force-tool quedaba sin efecto y el 14B se iba a
            # list_directory. Reducir antes (excluir + enfocar) lo evita y deja más sitio al hilo.
            _s = get_settings()
            _tool_choice = "auto"
            _tools_efectivas = tools_schema
            if _excl_run:
                _tools_efectivas = [
                    t for t in _tools_efectivas if t["function"]["name"] not in _excl_run
                ]
            if _intencion and run.step_count == 0:
                # PRIMER paso: enfoca a la tool correcta y fuérzala (tool_choice required).
                _foco = tools_foco(_intencion)
                # La intención está clasificada de forma DETERMINISTA → las tools del foco DEBEN
                # ofrecerse aunque select_tool_names no las activara por keywords (p.ej. «cuánto he
                # gastado» no casa 'factura', así que resumen_facturacion no se ofrecía y el 14B se
                # escapaba a buscar en la bandeja). Las añadimos si faltan, antes de filtrar.
                _ya = {t["function"]["name"] for t in _tools_efectivas}
                for _n in _foco - _ya:
                    try:
                        _tools_efectivas = _tools_efectivas + [loop.registry.get(_n).to_openai()]
                    except Exception:  # noqa: BLE001 — si la tool no existe, se ignora
                        pass
                _filtradas = [t for t in _tools_efectivas if t["function"]["name"] in _foco]
                if _filtradas:
                    _tools_efectivas = _filtradas
                    _tool_choice = "required"
            msgs_llm, tools_llm, _recortado = ajustar_a_contexto(
                run.messages,
                _tools_efectivas,
                n_ctx=_s.llm_context_length,
                max_tokens=_s.llm_max_tokens,
            )
            if _recortado:
                logger.info("ALG-0.1 recortó el contexto para que quepa run=%s", run.id)
            # Allowlist: el modelo solo puede ejecutar las tools OFRECIDAS en este paso. El 14B a
            # veces alucina un nombre de tool fuera del set (p.ej. registrar_factura cuando solo se
            # le dio plan_cobro). Si lo hace, se rechaza, no se ejecuta. Seguridad + fiabilidad.
            _ofrecidas = {t["function"]["name"] for t in tools_llm}
            response: ChatResponse = loop.llm.chat(
                messages=msgs_llm,
                tools=tools_llm,
                tool_choice=_tool_choice,
            )

            # Añadir respuesta del asistente al historial
            run.messages.append(response.to_message())

            # ── Caso: el LLM no quiere usar tools ─────────────────────────
            if not response.has_tool_calls:
                # El modelo a veces escribe el nombre de una tool (p.ej. "task_done")
                # como texto en vez de llamarla; lo quitamos antes de mostrar nada.
                content = _strip_tool_artifacts(response.content.strip())

                # Puede que devuelva el sentinel en texto plano
                done_result = _extract_sentinel(content, _SENTINEL_DONE)
                if done_result is not None:
                    done_result = loop._relay_fiel(run, done_result)
                    run.mark_completed(done_result)
                    _log_conversation_event(run, "completed", done_result)
                    _update_memory(run)
                    loop.store.save_run(run)
                    return run

                approval_result = _extract_sentinel(content, _SENTINEL_APPROVAL)
                if approval_result is not None:
                    parsed = _parse_approval_json(approval_result)
                    run.mark_pending_approval(
                        reason=parsed.get("reason", "Sin razón especificada"),
                        proposed_action=parsed.get("proposed_action", content),
                        tool_call_id="text_response",
                    )
                    loop.store.save_run(run)
                    return run

                # Respuesta de texto sin sentineles: seguimos (el LLM está razonando)
                # Si finish_reason=stop y no hay sentineles, asumimos tarea completada
                if response.finish_reason == "stop":
                    run.mark_completed(loop._relay_fiel(run, content or "(sin resultado)"))
                    _update_memory(run)
                    loop.store.save_run(run)
                    return run

                # finish_reason=length u otro: continuar el bucle
                loop.store.save_run(run)
                continue

            # ── Caso: el LLM quiere ejecutar tools ────────────────────────
            # Detección de bucle: si la misma tool se repite N veces seguidas
            _inject_loop_hint(run, response.tool_calls)

            tool_results: list[dict] = []
            pending_approval: dict | None = None

            for idx, tc in enumerate(response.tool_calls):
                step_num = run.step_count + 1
                if (_intencion or _excl_run) and tc.tool_name not in _ofrecidas:
                    # Con intención enfocada o exclusión activa, el 14B no puede invocar una tool
                    # fuera del set ofrecido (alucinaba registrar_factura/calendar_create): se rechaza.
                    result_text, needs_stop = (
                        f"ERROR al ejecutar '{tc.tool_name}': no disponible en este paso; "
                        "usa una de las herramientas ofrecidas.",
                        False,
                    )
                else:
                    result_text, needs_stop = loop._execute_tool_call(tc, step_num, run)

                step = AgentStep(
                    step=step_num,
                    tool_name=tc.tool_name,
                    tool_call_id=tc.id,
                    arguments=tc.arguments,
                    result=result_text,
                    requires_approval=needs_stop,
                )
                run.add_step(step)
                tool_results.append(tool_result_message(tc.id, result_text))

                if needs_stop:
                    # Placeholders para tool calls no procesadas
                    for remaining_tc in response.tool_calls[idx + 1 :]:
                        tool_results.append(
                            tool_result_message(remaining_tc.id, "Accion pospuesta.")
                        )
                    if not result_text.startswith(_SENTINEL_QUESTION):
                        parsed = _parse_approval_json(
                            result_text[len(_SENTINEL_APPROVAL) :]
                            if result_text.startswith(_SENTINEL_APPROVAL)
                            else result_text
                        )
                        pending_approval = {
                            "reason": parsed.get("reason", "Aprobacion requerida"),
                            "proposed_action": parsed.get("proposed_action", result_text),
                            "tool_call_id": tc.id,
                        }
                    break

            # §SEG-1/2 (datos≠órdenes): neutraliza inyecciones en lo LEÍDO antes de que el
            # contenido entre en el contexto que el LLM verá el turno siguiente.
            _blindar_tool_results(tool_results, run)
            run.messages.extend(tool_results)

            done_summary = _first_sentinel([tr["content"] for tr in tool_results], _SENTINEL_DONE)
            if done_summary is not None:
                run.mark_completed(loop._relay_fiel(run, done_summary))
                _update_memory(run)
                loop.store.save_run(run)
                return run

            if pending_approval:
                run.mark_pending_approval(
                    reason=pending_approval["reason"],
                    proposed_action=pending_approval["proposed_action"],
                    tool_call_id=pending_approval["tool_call_id"],
                )
                loop.store.save_run(run)
                return run

            question_payload = _first_sentinel(
                [tr["content"] for tr in tool_results], _SENTINEL_QUESTION
            )
            if question_payload is not None:
                parsed = _parse_approval_json(question_payload)
                question_tc_id = next(
                    (
                        tr.get("tool_call_id", "")
                        for tr in tool_results
                        if _SENTINEL_QUESTION in tr.get("content", "")
                    ),
                    "",
                )
                run.mark_pending_question(
                    question=parsed.get("question", question_payload),
                    tool_call_id=question_tc_id,
                )
                _log_conversation_event(
                    run, "agent_question", parsed.get("question", question_payload)
                )
                loop.store.save_run(run)
                return run

            # ── Anti-flailing: una tool que falla en seco repetidamente ───
            corte = loop._maybe_cut_for_flailing(run, response.tool_calls)
            if corte is not None:
                run.mark_failed(corte)
                loop._aprender_de_fallo(run)
                loop.store.save_run(run)
                return run

            loop.store.save_run(run)

    except Exception as exc:
        logger.exception("AgentLoop error en run=%s", run.id)
        run.mark_failed(f"Error inesperado: {exc}")
        loop._aprender_de_fallo(run)
        loop.store.save_run(run)
        return run
    finally:
        # Fin de la ejecución (completado, pausa o error): cerrar la sesión de halo;
        # el halo se apaga solo poco después. Al reanudar se reabre si vuelve a pilotar.
        from ..pilot import overlay_manager

        overlay_manager.stop_session()


def intentar_multi_intent(loop, run: AgentRun) -> bool:
    """A1: descompone una petición multi-intención de LECTURA, ejecuta cada métrica con su tool
    determinista y COMPONE una sola respuesta. Devuelve True si la resolvió (run completado);
    False si no aplica (→ sigue el flujo single-intent). Solo entran tools de lectura del MENU
    (sin efecto externo) → auto-ejecutarlas es seguro, no necesita aprobación."""
    subs = resolver(run.task, loop.llm)
    if len(subs) < 2:
        return False
    partes: list[str] = []
    for sub in subs:
        item = MENU.get(sub.intencion)
        if not item:
            continue
        try:
            td = loop.registry.get(item.tool)
            res = td.fn(**sub.args)
        except Exception as exc:  # noqa: BLE001 — que una métrica falle no tumba las demás
            logger.info("A1: fallo ejecutando %s (%s)", item.tool, exc)
            continue
        run.add_step(
            AgentStep(
                step=run.step_count + 1,
                tool_name=item.tool,
                tool_call_id=f"a1_{sub.intencion}",
                arguments=sub.args,
                result=res,
                requires_approval=False,
            )
        )
        if res and res.strip():
            partes.append(res.strip())
    if len(partes) < 2:
        return False  # no se compusieron ≥2 métricas → mejor el single-intent
    run.mark_completed("\n\n".join(partes))
    _log_conversation_event(run, "completed", run.result)
    _update_memory(run)
    loop.store.save_run(run)
    return True
