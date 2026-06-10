"""
AgentLoop — motor ReAct (Reason + Act) de Loombit.

Ciclo:
  1. system_prompt + task → LLM
  2. LLM devuelve contenido (stop) o tool_calls
  3. Si stop            → ¿es TASK_DONE? → terminar | si no, seguir
  4. Si tool_calls      → ejecutar cada tool → añadir resultados → volver a 2
  5. Si PENDING_APPROVAL en cualquier resultado → pausar
  6. Si exceeded_max_steps → marcar como failed

Sentineles detectados en el resultado de cualquier tool:
  "TASK_DONE:{summary}"        — tarea completada
  "PENDING_APPROVAL:{json}"    — necesita aprobación humana

El loop nunca llama directamente a tools externas; siempre va a través de
ToolRegistry.get(name).execute(**kwargs) para que los guards de aprobación
queden centralizados en la definición de la tool.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date
from typing import Any

from ..config import get_settings
from ..llm import ChatResponse, LLMClient, ToolCall, tool_result_message
from ..tools import tool_registry
from ..tools.registry import ToolRegistry
from .memory import get_memory
from .contexto import ajustar_a_contexto
from .descomposicion import MENU, resolver
from .intencion import (
    es_lectura_agenda,
    intencion_consecuente,
    tools_excluir,
    tools_foco,
)
from .parsers import parsear_fecha, validar_iban
from .prompts import build_system_prompt
from .run import AgentRun, AgentStatus, AgentStep, AgentStore

logger = logging.getLogger(__name__)

_SENTINEL_DONE = "TASK_DONE:"
_SENTINEL_APPROVAL = "PENDING_APPROVAL:"
_SENTINEL_QUESTION = "PENDING_QUESTION:"

# Anti-flailing: si la MISMA tool falla esta cantidad de veces SEGUIDAS, el bucle corta en seco
# (no quema los 20 pasos martilleando algo roto). El 1er fallo solo avisa; el 2º detiene.
_TOOL_ERROR_CUT = 2

# Prefijos con los que el propio bucle marca un resultado como ERROR de ejecución de tool (tool
# inexistente, argumentos inválidos, excepción, o fallo al ejecutar lo ya aprobado). Se centralizan
# aquí para que productor (_execute_tool_call / resume) y detector (_is_error_result) no se
# desincronicen.
_ERROR_PREFIXES = (
    "ERROR: tool desconocida",
    "ERROR: argumentos invalidos",
    "ERROR en '",
    "ERROR al ejecutar",
)

# El asunto/cuerpo de un correo los redacta el agente, no el usuario. Si el modelo intenta
# preguntarlos vía ask_user, lo interceptamos y le devolvemos la orden de redactarlos él.
_PREGUNTA_AUTORREDACTABLE = re.compile(r"asunto|subject|cuerpo|\bbody\b|t[ií]tulo del correo", re.I)

# F4 — el correo lo firma el usuario; el agente NO se delata como IA/bot. Guarda determinista
# que bloquea un correo que se auto-identifica como automático (apunta a la auto-revelación, no a
# menciones temáticas de "IA": Fernando podría vender servicios de IA).
_DELATA_BOT = re.compile(
    r"soy (un |una )?(agente|asistente virtual|bot|ia\b|inteligencia artificial|operador (de ia|aut))"
    r"|asistid[oa] por (un|una) (agente|ia)|agente aut[oó]nomo|agente virtual|loombit operator"
    r"|correo autom[aá]tico|mensaje autom[aá]tico|enviado por un agente"
    r"|generad[oa] autom[aá]ticamente|soy tu asistente (personal|virtual)",
    re.I,
)


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


class AgentLoop:
    """
    Motor síncrono de ejecución del agente.

    Uso mínimo:
        loop = AgentLoop()
        run = loop.run("Resume los correos de hoy y guárdalos en resumen.txt")
        print(run.status, run.result)
    """

    def __init__(
        self,
        llm: LLMClient | None = None,
        registry: ToolRegistry | None = None,
        store: AgentStore | None = None,
        max_steps: int = 20,
    ) -> None:
        self.llm = llm or LLMClient()
        self.registry = registry or tool_registry
        self.store = store or AgentStore()
        self.max_steps = max_steps

    # ── API pública ───────────────────────────────────────────────────────────

    def run(self, task: str) -> AgentRun:
        """Crea un AgentRun nuevo y ejecuta el bucle hasta completar o pausar."""
        agent_run = self.store.create(task, max_steps=self.max_steps)
        return self._execute(agent_run)

    def create(
        self,
        task: str,
        max_steps: int | None = None,
        profile: str = "administrativo",
        history: list[dict] | None = None,
    ) -> AgentRun:
        """Crea un AgentRun sin ejecutarlo — para lanzar en background.

        `history` son los turnos previos de la conversación
        (`[{"role": "user"|"assistant", "content": str}, ...]`). Se siembran ANTES de la
        tarea actual para que el agente tenga MEMORIA del hilo: así un "sí" sabe a qué
        responde, en vez de nacer de cero (la causa del fallo de amnesia del chat).
        """
        run = self.store.create(task, max_steps=max_steps or self.max_steps)
        run.profile = profile
        # Pasar la tarea como hint para que la memoria incluya procedimientos relevantes
        memory_block = get_memory().to_context_block(task_hint=task)
        messages: list[dict] = [
            {"role": "system", "content": build_system_prompt(profile, memory_block)}
        ]
        for turn in history or []:
            role = turn.get("role")
            content = turn.get("content")
            if role in ("user", "assistant") and isinstance(content, str) and content.strip():
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": task})
        run.messages = messages
        self.store.save_run(run)
        return run

    def execute_run(self, run_id: str) -> AgentRun:
        """Ejecuta un run ya creado — seguro para llamar desde un thread."""
        run = self.store.get(run_id)
        return self._execute(run)

    def accept_approval(self, run_id: str) -> AgentRun:
        """SÍNCRONO y rápido: acepta la aprobación humana y deja el run en RUNNING. NO ejecuta la
        tool aprobada ni el LLM — de eso se encarga `_resume_execute` (en background). Separar la
        ACEPTACIÓN (instantánea) de la EJECUCIÓN evita la ventana de carrera en la que la UI recibía
        el run aún en `pending_approval` y volvía a pintar la misma tarjeta."""
        run = self.store.get(run_id)
        if run.status != AgentStatus.PENDING_APPROVAL:
            raise ValueError(f"El run {run_id} no está en pending_approval (status={run.status})")
        run.approve()  # → RUNNING; limpia pending_approval. Los steps a ejecutar siguen marcados.
        self.store.save_run(run)
        return run

    def resume(self, run_id: str) -> AgentRun:
        """Acepta la aprobación y ejecuta hasta el siguiente hito (uso directo y en tests)."""
        self.accept_approval(run_id)
        return self._resume_execute(run_id)

    def _resume_execute(self, run_id: str) -> AgentRun:
        """Ejecuta la(s) tool(s) ya aprobada(s) y continúa el bucle. Asume que el run YA está en
        RUNNING (lo dejó `accept_approval`). Reemplaza cada placeholder PENDING_APPROVAL del
        historial por el resultado real antes de seguir."""
        run = self.store.get(run_id)

        # Ejecutar TODOS los steps que están esperando aprobación
        pending_steps = [
            s for s in run.steps if s.requires_approval and s.result.startswith(_SENTINEL_APPROVAL)
        ]
        for pending_step in pending_steps:
            logger.info(
                "Resume: ejecutando tool aprobada '%s' (step %d) run=%s",
                pending_step.tool_name,
                pending_step.step,
                run_id,
            )
            try:
                tool_def = self.registry.get(pending_step.tool_name)
                actual_result = str(tool_def.execute(**pending_step.arguments))
            except Exception as exc:
                actual_result = f"ERROR al ejecutar '{pending_step.tool_name}': {exc}"

            # Actualizar el step con el resultado real
            pending_step.result = actual_result
            pending_step.requires_approval = False

            # Reemplazar el mensaje PENDING_APPROVAL en el historial del LLM
            tc_id = pending_step.tool_call_id
            for msg in run.messages:
                if msg.get("role") == "tool" and msg.get("tool_call_id") == tc_id:
                    msg["content"] = actual_result
                    break

        # Si la acción que el usuario YA APROBÓ falló al ejecutarse, NO re-pausamos en silencio:
        # se lo decimos al modelo para que la corrija UNA vez o lo explique con task_done, en lugar
        # de volver a sacar la misma tarjeta a ciegas (el bug de "la ventanita que reaparece").
        fallos_aprobados = [s for s in pending_steps if _is_error_result(s.result)]

        if fallos_aprobados:
            detalle = "; ".join(
                f"«{s.tool_name}» → {_error_brief(s.result)}" for s in fallos_aprobados
            )
            run.messages.append(
                {
                    "role": "user",
                    "content": (
                        f"[SISTEMA: La acción que el usuario YA APROBÓ falló al ejecutarse "
                        f"({detalle}). NO vuelvas a pedir la misma aprobación a ciegas. Si puedes "
                        f"corregir el problema de forma determinista (p. ej. un argumento), hazlo "
                        f"UNA sola vez; si no, explica el fallo al usuario con task_done. No repitas "
                        f"la acción idéntica.]"
                    ),
                }
            )
        self.store.save_run(run)
        return self._execute(run)

    def accept_answer(self, run_id: str, answer_text: str) -> AgentRun:
        """SÍNCRONO y rápido: inyecta la respuesta del usuario EN EL SITIO de la pregunta y deja el
        run en RUNNING. NO ejecuta el LLM — de eso se encarga `execute_run` (en background). Separar
        la ACEPTACIÓN de la EJECUCIÓN evita que la UI reciba el run aún en `pending_question` y vuelva
        a pintar la misma pregunta (el bug de «me preguntó la hora dos veces»)."""
        run = self.store.get(run_id)
        if run.status != AgentStatus.PENDING_QUESTION:
            raise ValueError(f"El run {run_id} no está en pending_question (status={run.status})")

        # Reemplazar el resultado PENDING_QUESTION en el historial por la respuesta real
        tc_id = run.pending_question.get("tool_call_id", "")
        answer_result = f"Usuario respondió: {answer_text}"

        for step in run.steps:
            if step.tool_call_id == tc_id and step.result.startswith(_SENTINEL_QUESTION):
                step.result = answer_result
                step.requires_approval = False

        for msg in run.messages:
            if msg.get("role") == "tool" and msg.get("tool_call_id") == tc_id:
                msg["content"] = answer_result
                break

        # Añadir la respuesta como mensaje de usuario al historial del LLM
        run.messages.append({"role": "user", "content": answer_text})

        run.answer()  # → RUNNING; limpia pending_question
        self.store.save_run(run)
        _log_conversation_event(run, "user_answer", answer_text)
        return run

    def answer(self, run_id: str, answer_text: str) -> AgentRun:
        """Inyecta la respuesta y reanuda el agente hasta el siguiente hito (uso directo y tests)."""
        self.accept_answer(run_id, answer_text)
        return self.execute_run(run_id)

    # ── Motor interno ─────────────────────────────────────────────────────────

    def _execute(self, run: AgentRun) -> AgentRun:
        run.mark_running()
        self.store.save_run(run)

        # Primer mensaje si es un run nuevo (sin historial). SIEMPRE con la memoria (dueño +
        # lecciones): sin ella el modelo se inventa la identidad (firmó "José Martínez" en vez de
        # Fernando). El dueño/firma es contexto, no se deja al azar.
        if not run.messages:
            memory_block = get_memory().to_context_block(task_hint=run.task)
            run.messages = [
                {"role": "system", "content": build_system_prompt(run.profile, memory_block)},
                {"role": "user", "content": run.task},
            ]

        # Retención IRPF no modelada: si la petición es REGISTRAR/PREPARAR una factura/minuta CON
        # retención, NO entramos al ReAct (el 14B fabrica un «preparada» con cifras erróneas —tratando
        # la retención como IVA—, visto en la presión del arnés). Respuesta honesta y determinista
        # ANTES de gastar el bucle. Hasta construir el 130 (#8/#9).
        if _es_registro_con_retencion(run.task):
            logger.info("registro con retención IRPF no modelada → rehúso honesto run=%s", run.id)
            run.mark_completed(_MSG_RETENCION_NO_MODELADA)
            _log_conversation_event(run, "completed", run.result)
            self.store.save_run(run)
            return run

        # IBAN inválido a guardar: no fabricamos un «guardado» de un IBAN que no cuadra (checksum).
        if _iban_invalido_a_guardar(run.task):
            logger.info("IBAN inválido a guardar → rehúso honesto run=%s", run.id)
            run.mark_completed(_MSG_IBAN_INVALIDO)
            _log_conversation_event(run, "completed", run.result)
            self.store.save_run(run)
            return run

        # Modelo AEAT no modelado (111/349/130…): abstención honesta ANTES del ReAct (no confundir con
        # el 303 ni fabricar). El 303 sí se modela y NO entra aquí.
        _mod_na = _modelo_no_modelado(run.task)
        if _mod_na:
            logger.info("modelo %s no modelado → abstención honesta run=%s", _mod_na, run.id)
            run.mark_completed(_MSG_MODELO_NO_MODELADO.format(m=_mod_na))
            _log_conversation_event(run, "completed", run.result)
            self.store.save_run(run)
            return run

        try:
            tools_schema = self.registry.to_openai(profile=run.profile, task=run.task)
            # P0 fiabilidad: en intenciones consecuentes (cobro/303/factura/buscar) el 14B a veces
            # calcula/contesta a ojo (fabrica) o llama a la tool equivocada. En el PRIMER paso forzamos
            # la tool Y la enfocamos a la correcta. Solo si la petición trae datos (si no, que pregunte).
            # En conversación, una respuesta corta hereda la intención del turno anterior (ver
            # _texto_para_intencion) → un «Emitida.» fuerza registrar_factura en vez de fabricar.
            _intencion = intencion_consecuente(_texto_para_intencion(run))
            # A1 (gate de ambigüedad INTERNO): si la petición cruza varias intenciones de LECTURA
            # (cross-domain, p.ej. financiero + agenda), se descompone, se ejecuta cada métrica con su
            # tool determinista y se compone UNA respuesta aquí — sin preguntar al usuario. Si no
            # aplica (mono-intención), sigue el flujo single-intent de abajo (0 regresión).
            if self._intentar_multi_intent(run):
                return run
            # Exclusiones para TODO el run: otras tools de dominio + (si es pregunta de agenda)
            # calendar_create, para que una LECTURA no acabe creando un evento.
            _excl_run = tools_excluir(_intencion)
            if es_lectura_agenda(run.task):
                _excl_run = _excl_run | {"calendar_create"}
            while True:
                # Guard: cancelación externa (el usuario pulsó "Detener")
                fresh = self.store.get(run.id)
                if fresh.status == AgentStatus.CANCELLED:
                    return fresh

                # Guard: límite de pasos
                if run.exceeded_max_steps:
                    run.mark_failed(
                        f"Límite de {run.max_steps} pasos alcanzado sin completar la tarea."
                    )
                    self._aprender_de_fallo(run)
                    self.store.save_run(run)
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
                            _tools_efectivas = _tools_efectivas + [
                                self.registry.get(_n).to_openai()
                            ]
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
                response: ChatResponse = self.llm.chat(
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
                        done_result = self._relay_fiel(run, done_result)
                        run.mark_completed(done_result)
                        _log_conversation_event(run, "completed", done_result)
                        _update_memory(run)
                        self.store.save_run(run)
                        return run

                    approval_result = _extract_sentinel(content, _SENTINEL_APPROVAL)
                    if approval_result is not None:
                        parsed = _parse_approval_json(approval_result)
                        run.mark_pending_approval(
                            reason=parsed.get("reason", "Sin razón especificada"),
                            proposed_action=parsed.get("proposed_action", content),
                            tool_call_id="text_response",
                        )
                        self.store.save_run(run)
                        return run

                    # Respuesta de texto sin sentineles: seguimos (el LLM está razonando)
                    # Si finish_reason=stop y no hay sentineles, asumimos tarea completada
                    if response.finish_reason == "stop":
                        run.mark_completed(self._relay_fiel(run, content or "(sin resultado)"))
                        _update_memory(run)
                        self.store.save_run(run)
                        return run

                    # finish_reason=length u otro: continuar el bucle
                    self.store.save_run(run)
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
                        result_text, needs_stop = self._execute_tool_call(tc, step_num, run)

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

                run.messages.extend(tool_results)

                done_summary = _first_sentinel(
                    [tr["content"] for tr in tool_results], _SENTINEL_DONE
                )
                if done_summary is not None:
                    run.mark_completed(self._relay_fiel(run, done_summary))
                    _update_memory(run)
                    self.store.save_run(run)
                    return run

                if pending_approval:
                    run.mark_pending_approval(
                        reason=pending_approval["reason"],
                        proposed_action=pending_approval["proposed_action"],
                        tool_call_id=pending_approval["tool_call_id"],
                    )
                    self.store.save_run(run)
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
                    self.store.save_run(run)
                    return run

                # ── Anti-flailing: una tool que falla en seco repetidamente ───
                corte = self._maybe_cut_for_flailing(run, response.tool_calls)
                if corte is not None:
                    run.mark_failed(corte)
                    self._aprender_de_fallo(run)
                    self.store.save_run(run)
                    return run

                self.store.save_run(run)

        except Exception as exc:
            logger.exception("AgentLoop error en run=%s", run.id)
            run.mark_failed(f"Error inesperado: {exc}")
            self._aprender_de_fallo(run)
            self.store.save_run(run)
            return run
        finally:
            # Fin de la ejecución (completado, pausa o error): cerrar la sesión de halo;
            # el halo se apaga solo poco después. Al reanudar se reabre si vuelve a pilotar.
            from ..pilot import overlay_manager

            overlay_manager.stop_session()

    def _intentar_multi_intent(self, run: AgentRun) -> bool:
        """A1: descompone una petición multi-intención de LECTURA, ejecuta cada métrica con su tool
        determinista y COMPONE una sola respuesta. Devuelve True si la resolvió (run completado);
        False si no aplica (→ sigue el flujo single-intent). Solo entran tools de lectura del MENU
        (sin efecto externo) → auto-ejecutarlas es seguro, no necesita aprobación."""
        subs = resolver(run.task, self.llm)
        if len(subs) < 2:
            return False
        partes: list[str] = []
        for sub in subs:
            item = MENU.get(sub.intencion)
            if not item:
                continue
            try:
                td = self.registry.get(item.tool)
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
        self.store.save_run(run)
        return True

    def _accion_fallida_sin_exito(self, run: AgentRun) -> bool:
        """True si en el run se INTENTÓ alguna tool con EFECTO real (persistir/enviar/crear) y NINGUNA
        de ellas tuvo éxito (todas erraron) → la acción del usuario NO ocurrió, así que no se puede
        presentar un éxito. Solo cuentan las de efecto (no las de lectura: un 303-lectura «con éxito»
        sobre entidad vacía no significa que se registrara la factura que pedía el usuario)."""
        intentos = [s for s in run.steps if s.tool_name in _TOOLS_EFECTO]
        return bool(intentos) and all(_paso_es_fallo(s) for s in intentos)

    def _relay_fiel(self, run: AgentRun, result: str) -> str:
        """ALG-4.1 (relay fiel): garantiza que la salida VERBATIM de CADA tool AUTORITATIVA
        (cálculo determinista: cobro, 303, factura) está en el resultado, aunque el LLM la haya
        parafraseado. Así las cifras que ve el usuario == las que calculó el código. Recoge TODAS
        en orden (no solo la última): si se registran N facturas, el usuario ve las N, no una."""
        # DoD (no mentir): si toda acción material falló pero el texto afirma éxito, lo corregimos
        # por un mensaje honesto (no inventamos un «✅ hecho» que no ocurrió). Ver _afirma_exito.
        if self._accion_fallida_sin_exito(run) and _afirma_exito(result):
            return _con_aviso_regulado(getattr(run, "task", ""), _MENSAJE_FALLO_HONESTO)
        autoritativos: list[str] = []
        for s in run.steps:  # en ORDEN de ejecución
            try:
                td = self.registry.get(s.tool_name)
            except Exception:
                continue
            if not getattr(td, "authoritative", False) or _is_error_result(s.result):
                continue
            verbatim = (s.result or "").strip()
            if verbatim and verbatim not in (result or "") and verbatim not in autoritativos:
                autoritativos.append(verbatim)
        if autoritativos:
            bloque = "\n\n".join(autoritativos)
            result = bloque + ("\n\n" + result if result and result.strip() else "")
        # Aviso determinista en preguntas fiscales reguladas (getattr: los tests pasan run sin .task).
        return _con_aviso_regulado(getattr(run, "task", ""), result)

    def _execute_tool_call(self, tc: ToolCall, step_num: int, run: AgentRun) -> tuple[str, bool]:
        try:
            tool_def = self.registry.get(tc.tool_name)
        except KeyError:
            return f"ERROR: tool desconocida '{tc.tool_name}'", False

        # Retención IRPF no modelada: NO registramos en silencio una factura con retención (falsearía
        # el 303 y el 111/130). Se rehúsa honesto ANTES de ejecutar — hasta construir el 130 (#8/#9).
        if tc.tool_name == "registrar_factura" and _lleva_retencion(run.task, tc.arguments):
            logger.info("registrar_factura: rehusada por retención IRPF no modelada run=%s", run.id)
            return _MSG_RETENCION_NO_MODELADA, False

        # ALG anti-fabricación del 303: el 14B mete líneas inventadas; quita las que no estén en el
        # mensaje del usuario (su base no aparece) ANTES de calcular. Determinista.
        if tc.tool_name == "calcular_303":
            tc.arguments, _q303 = _filtrar_lineas_303(tc.arguments, run.task)
            if _q303:
                logger.info("303: descartadas %d línea(s) inventada(s) run=%s", _q303, run.id)

        # ALG fecha-fiel: el 14B yerra fechas relativas ('próximo lunes'); las recalcula el código.
        if tc.tool_name == "calendar_create" and _corregir_fecha_calendario(tc.arguments, run.task):
            logger.info("calendar_create: fecha relativa corregida run=%s", run.id)
        if tc.tool_name == "plan_cobro" and _corregir_fecha_cobro(tc.arguments, run.task):
            logger.info("plan_cobro: fecha de vencimiento relativa corregida run=%s", run.id)
        if tc.tool_name in ("calcular_303", "calcular_303_registradas") and _corregir_periodo_303(
            tc.arguments, run.task
        ):
            logger.info("303: periodo (trimestre) puesto al actual run=%s", run.id)
        if tc.tool_name == "resumen_financiero" and _corregir_trimestre_relativo(
            tc.arguments, run.task
        ):
            logger.info("resumen_financiero: trimestre relativo puesto al actual run=%s", run.id)

        # Señal visible PERSISTENTE: si el agente usa una tool de pilotaje (escritorio/navegador),
        # abre la sesión de halo → el usuario VE a Loombit pilotando durante todo el run.
        if tool_def.category in ("pilot", "computer"):
            from ..pilot import overlay_manager

            overlay_manager.start_session()

        # Guarda 12-factor (F2): el destinatario es un IDENTIFICADOR, no se confía al modelo.
        # Solo se permite enviar a un email que el usuario escribió o que se resolvió con
        # contacts_find en este run. Inventarlo se bloquea ANTES de la tarjeta de aprobación.
        if tc.tool_name == "gmail_send" and not _recipiente_resuelto(
            str(tc.arguments.get("to", "")), run
        ):
            logger.info("gmail_send a destinatario no resuelto run=%s", run.id)
            return (
                f"[SISTEMA: No envíes a «{tc.arguments.get('to', '')}»: no es un email que el "
                "usuario te haya dado ni uno resuelto con contacts_find. NO inventes destinatarios. "
                "Llama a contacts_find con el nombre y usa el email del contacto correcto; si hay "
                "varios, elige el más probable o pregunta; si no aparece, pregunta al usuario.]",
                False,
            )

        # Guarda F4: el correo no puede delatarse como IA/bot. Se corrige ANTES de la aprobación.
        if tc.tool_name == "gmail_send" and _DELATA_BOT.search(
            f"{tc.arguments.get('subject', '')} {tc.arguments.get('body', '')}"
        ):
            logger.info("gmail_send se delata como bot — corrigiendo run=%s", run.id)
            return (
                "[SISTEMA: El correo se presenta como IA/agente/automático. Reescríbelo COMO el "
                "usuario (primera persona), sin mencionar que eres un asistente, agente o bot ni "
                "que el correo es automático. Fírmalo con el nombre del usuario.]",
                False,
            )

        # Política de aprobación: un correo que el USUARIO pidió y con destinatario inequívoco
        # se envía SOLO (sin tarjeta) — su petición es la autorización. Si el destinatario es
        # ambiguo, se confirma. Otros efectos externos (calendar_create, run_shell) siempre confirman.
        auto_envio_correo = (
            tc.tool_name == "gmail_send"
            and not getattr(run, "proactive", False)  # lo proactivo SIEMPRE se confirma
            and _destinatario_claro(str(tc.arguments.get("to", "")), run)
        )
        if tool_def.requires_approval and not auto_envio_correo:
            reason, proposed = _describe_for_approval(tc.tool_name, tc.arguments)
            payload = json.dumps({"reason": reason, "proposed_action": proposed})
            return f"{_SENTINEL_APPROVAL}{payload}", True

        logger.info("Ejecutando tool '%s' step=%d run=%s", tc.tool_name, step_num, run.id)
        try:
            result = tool_def.execute(**tc.arguments)
        except TypeError as exc:
            return f"ERROR: argumentos invalidos para '{tc.tool_name}': {exc}", False
        except Exception as exc:
            return f"ERROR en '{tc.tool_name}': {exc}", False

        result_text = str(result)

        if result_text.startswith(_SENTINEL_APPROVAL):
            return result_text, True
        if result_text.startswith(_SENTINEL_QUESTION):
            # Barrera: nunca molestamos al usuario con el asunto/cuerpo de un correo.
            # Si el modelo lo pregunta, lo autocorregimos y seguimos (sin pausar).
            if tc.tool_name == "ask_user" and _PREGUNTA_AUTORREDACTABLE.search(
                str(tc.arguments.get("question", ""))
            ):
                logger.info(
                    "ask_user interceptado (asunto/cuerpo) — autocorrigiendo run=%s", run.id
                )
                return (
                    "[SISTEMA: No se pregunta el asunto ni el cuerpo de un correo. "
                    "Redáctalos TÚ a partir del encargo y continúa hasta gmail_send "
                    "(que pedirá la aprobación de envío). No vuelvas a preguntar esto.]",
                    False,
                )
            return result_text, True

        if tc.tool_name == "gmail_search":
            try:
                parsed = json.loads(result_text)
                if parsed.get("ok") and parsed.get("count", 0) == 0:
                    hint = (
                        result_text + "\n"
                        "[SISTEMA: 0 resultados. Prueba terminos distintos: "
                        "nombre parcial, dominio, asunto, fecha. No preguntes al usuario.]"
                    )
                    return hint, False
            except (json.JSONDecodeError, AttributeError):
                pass

        return result_text, False

    def _maybe_cut_for_flailing(self, run: AgentRun, tool_calls: list[ToolCall]) -> str | None:
        """Anti-flailing. Si una tool acaba de fallar por 2ª vez SEGUIDA, devuelve el mensaje de
        corte honesto (el bucle marcará el run como fallido en vez de quemar pasos). Si es el 1er
        fallo, inyecta un aviso preciso para que el modelo cambie antes de gastar otro paso.
        Devuelve None si no hay que cortar."""
        for tc in tool_calls:
            fallos = _consecutive_tool_errors(run, tc.tool_name)
            ultimo = next((s for s in reversed(run.steps) if s.tool_name == tc.tool_name), None)
            if fallos >= _TOOL_ERROR_CUT:
                causa = _error_brief(ultimo.result) if ultimo else "error desconocido"
                logger.warning(
                    "Anti-flailing: corto run=%s tool='%s' x%d", run.id, tc.tool_name, fallos
                )
                return (
                    f"No pude completar la tarea: la herramienta «{tc.tool_name}» falló "
                    f"{fallos} veces seguidas y dejé de intentarlo. Causa: {causa}"
                )
            if fallos == 1 and ultimo is not None:
                run.messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"[SISTEMA: «{tc.tool_name}» falló: {_error_brief(ultimo.result)}. "
                            f"Si la herramienta no existe o no encaja, NO la vuelvas a llamar igual: "
                            f"usa otra vía o termina con task_done explicando la limitación. "
                            f"Un 2º fallo idéntico me detendrá.]"
                        ),
                    }
                )
        return None

    def _aprender_de_fallo(self, run: AgentRun) -> None:
        """Reflexión (sin fine-tuning): saca una lección general del fallo y la guarda en memoria.
        Best-effort — nunca rompe el run. La lección se recuperará en tareas futuras parecidas."""
        try:
            from .reflexion import etiquetas_de_tarea, reflexionar

            leccion = reflexionar(run, self.llm)
            if leccion:
                get_memory().add_lesson(
                    leccion, tags=etiquetas_de_tarea(run.task), outcome="fallo", source="reflexion"
                )
                logger.info("Lección aprendida (run=%s): %s", run.id, leccion[:80])
        except Exception:
            logger.debug("aprender_de_fallo best-effort falló", exc_info=True)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _recipiente_resuelto(to: str, run: AgentRun) -> bool:
    """True si el email destinatario es legítimo: lo escribió el usuario en su petición, o se
    resolvió con contacts_find en este run. Nunca se acepta un email "inventado" por el modelo
    ni uno auto-capturado en memoria (eso fue el bug de `jana.espinal`). Determinista, fail-closed.
    """
    to_l = to.strip().lower()
    if not to_l or "@" not in to_l:
        return False
    if to_l in (run.task or "").lower():
        return True
    return any(
        s.tool_name == "contacts_find" and to_l in (s.result or "").lower() for s in run.steps
    )


def _destinatario_claro(to: str, run: AgentRun) -> bool:
    """True si el destinatario es INEQUÍVOCO: lo escribió el usuario en su petición, o
    contacts_find lo resolvió SIN ambigüedad (estado='resuelto' y es el `mejor`). Si hubo
    ambigüedad (varios candidatos) devuelve False → se confirma con tarjeta. Más estricto que
    `_recipiente_resuelto` (que solo descarta inventados): aquí exigimos que NO haya duda.
    """
    to_l = to.strip().lower()
    if not to_l or "@" not in to_l:
        return False
    if to_l in (run.task or "").lower():
        return True
    # el usuario lo escribió en alguna respuesta del chat (p.ej. al desambiguar)
    for m in getattr(run, "messages", None) or []:
        if m.get("role") == "user" and to_l in (m.get("content", "") or "").lower():
            return True
    for s in run.steps:
        if s.tool_name != "contacts_find":
            continue
        try:
            data = json.loads(s.result)
        except Exception:
            continue
        if data.get("estado") == "resuelto":
            mejor = data.get("mejor") or {}
            if str(mejor.get("email", "")).strip().lower() == to_l:
                return True
    return False


def _describe_for_approval(tool_name: str, args: dict[str, Any]) -> tuple[str, str]:
    """Texto HUMANO para la tarjeta de aprobación: describe la acción real, no la tool.

    Devuelve (reason, proposed_action). El usuario aprueba "enviar este correo a X", no
    "ejecutar la tool gmail_send".
    """
    if tool_name == "gmail_send":
        to = str(args.get("to", "")).strip()
        subject = str(args.get("subject", "")).strip()
        body = str(args.get("body", "")).strip()
        cuerpo = body if len(body) <= 600 else body[:600] + "…"
        return (
            f"Enviar un correo a {to}" if to else "Enviar un correo",
            f"Para: {to}\nAsunto: {subject}\n\n{cuerpo}",
        )
    if tool_name == "calendar_create":
        # La tool usa `title` (no `summary`): leer el nombre real para que el borrador no salga vacío.
        titulo = str(args.get("title") or args.get("summary") or "").strip()
        start = str(args.get("start_iso", "")).strip()
        dur = args.get("duration_minutes")
        loc = str(args.get("location", "")).strip()
        detalle = f"Evento: {titulo or '(sin título)'}\nInicio: {start}"
        if dur:
            detalle += f"\nDuración: {dur} min"
        if loc:
            detalle += f"\nLugar: {loc}"
        return ("Crear un evento en tu calendario", detalle)
    if tool_name == "run_shell":
        return ("Ejecutar un comando en tu equipo", str(args.get("command", "")))
    # Genérico para cualquier otra tool sensible.
    return (
        f"Confirmar la acción «{tool_name}»",
        json.dumps(args, ensure_ascii=False, indent=2),
    )


def _strip_tool_artifacts(text: str) -> str:
    """Quita líneas sueltas que sean SOLO el nombre de una tool. A veces el modelo
    escribe 'task_done' (u otro nombre de tool) como texto al final del mensaje en vez
    de llamar a la tool. Son identificadores snake_case, nunca prosa de usuario → se
    eliminan sin tocar el mensaje real (que el usuario sí debe ver)."""
    from ..tools import tool_registry

    nombres = {t.name for t in tool_registry.list()}
    lineas = [
        ln for ln in text.splitlines() if ln.strip().strip("`*_-•().:").strip() not in nombres
    ]
    return "\n".join(lineas).strip()


def _extract_sentinel(text: str, prefix: str) -> str | None:
    if text.startswith(prefix):
        return text[len(prefix) :]
    return None


def _first_sentinel(texts: list[str], prefix: str) -> str | None:
    for t in texts:
        result = _extract_sentinel(t, prefix)
        if result is not None:
            return result
    return None


def _parse_approval_json(payload: str) -> dict[str, Any]:
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return {"reason": payload, "proposed_action": payload, "question": payload}


def _log_conversation_event(run: "AgentRun", event_type: str, content: str) -> None:
    try:
        from pathlib import Path
        from datetime import UTC, datetime

        ts = datetime.now(UTC)
        date_str = ts.strftime("%Y-%m-%d")
        conv_dir = Path("runtime/local/conversations")
        conv_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{date_str}_{run.id[:8]}.jsonl"
        event = json.dumps(
            {
                "ts": ts.isoformat(),
                "run_id": run.id,
                "task": run.task[:120],
                "event": event_type,
                "content": content,
            },
            ensure_ascii=False,
        )
        with open(conv_dir / filename, "a", encoding="utf-8") as f:
            f.write(event + "\n")
    except Exception:
        pass


def _numeros_del_texto(texto: str) -> set[str]:
    """Números del mensaje, normalizados (sin separadores de miles) para comparar bases."""
    out: set[str] = set()
    for m in re.findall(r"\d[\d.,]*", texto or ""):
        out.add(m.rstrip(".,").replace(".", "").replace(",", ""))
    return out


# Si el usuario escribió importes EN PALABRAS (mil, quinientos…), no podemos comparar bases por
# dígitos sin convertirlos → el filtro se desactiva para no tirar líneas legítimas (falso positivo).
_NUM_EN_PALABRAS = re.compile(
    r"\b(mil|cien|ciento|doscient\w+|trescient\w+|cuatrocient\w+|quinient\w+|"
    r"seiscient\w+|setecient\w+|ochocient\w+|novecient\w+)\b"
)


def _filtrar_lineas_303(args: dict, task: str) -> tuple[dict, int]:
    """ALG anti-fabricación del 303: quita las líneas cuya BASE no aparece en el mensaje del usuario
    (el 14B inventa líneas plausibles, p.ej. 'servicios 5000€'). Determinista. Devuelve (args, n_quitadas).
    No filtra si el usuario dio las cifras en palabras (evita falsos positivos).
    """
    t = (task or "").lower()
    nums = _numeros_del_texto(t)
    if not nums or _NUM_EN_PALABRAS.search(t):
        return args, 0
    quitadas = 0
    for campo in ("iva_repercutido", "iva_soportado"):
        lineas = args.get(campo)
        if not isinstance(lineas, list):
            continue
        nuevas = []
        for ln in lineas:
            try:
                base = str(int(float(ln.get("base"))))
            except (TypeError, ValueError):
                nuevas.append(ln)
                continue
            if base in nums:
                nuevas.append(ln)
            else:
                quitadas += 1
        args[campo] = nuevas
    return args, quitadas


_REL_FECHA = re.compile(
    r"\b(mañana|manana|pasado\s+mañana|pasado\s+manana|hoy|lunes|martes|mi[eé]rcoles|jueves|"
    r"viernes|s[aá]bado|domingo|que\s+viene|pr[oó]xim\w+)\b"
    r"|hace\s+\w+\s+(?:d[ií]as?|semanas?|mes(?:es)?)"
)


def _corregir_fecha_calendario(args: dict, task: str, hoy: date | None = None) -> bool:
    """ALG fecha-fiel: el 14B se equivoca con fechas relativas ('próximo lunes'→sábado). Si el task
    trae una fecha relativa, la recalcula con parsear_fecha (determinista) y corrige el `start_iso`
    (mantiene la HORA del modelo). Devuelve True si corrigió. Solo actúa si hay marcador relativo.
    """
    t = (task or "").lower()
    if not _REL_FECHA.search(t):
        return False
    fecha = parsear_fecha(t, hoy)
    if fecha is None:
        return False
    iso = str(args.get("start_iso") or "")
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})([T ].*)?$", iso)
    if not m:
        return False
    fecha_14b = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    nueva = fecha.isoformat()
    if fecha_14b == nueva:
        return False
    args["start_iso"] = nueva + (m.group(4) or "T09:00:00Z")
    return True


def _corregir_fecha_cobro(args: dict, task: str, hoy: date | None = None) -> bool:
    """ALG fecha-fiel (cobro): corrige `fecha_vencimiento` si el task trae una fecha relativa
    ('venció hace tres semanas'). El 14B la calcula mal (21→24 días) y eso cambia etapa e interés.
    """
    t = (task or "").lower()
    if not _REL_FECHA.search(t):
        return False
    fecha = parsear_fecha(t, hoy)
    if fecha is None:
        return False
    m = re.match(r"(\d{4}-\d{2}-\d{2})", str(args.get("fecha_vencimiento") or ""))
    actual = m.group(1) if m else ""
    nueva = fecha.isoformat()
    if actual == nueva:
        return False
    args["fecha_vencimiento"] = nueva
    return True


_TRIMESTRE_USUARIO = re.compile(
    r"\b[1-4]\s*[ºo]?\s*t\b|\bt[1-4]\b|(primer|segundo|tercer|cuarto)\s+trimestre", re.I
)


def _trimestre_actual(hoy: date | None = None) -> str:
    h = hoy or date.today()
    return f"{(h.month - 1) // 3 + 1}T {h.year}"


def _corregir_periodo_303(args: dict, task: str, hoy: date | None = None) -> bool:
    """Si el usuario NO especificó trimestre, usa el ACTUAL (desde la fecha), no la adivinanza del
    14B ('Primer trimestre' en junio). Determinista. Devuelve True si cambió el periodo."""
    if _TRIMESTRE_USUARIO.search(task or ""):
        return False  # el usuario indicó el trimestre → respétalo
    actual = _trimestre_actual(hoy)
    if str(args.get("periodo") or "").strip() == actual:
        return False
    args["periodo"] = actual
    return True


_TRIMESTRE_RELATIVO = re.compile(
    r"\b(este|el|nuestro)\s+trimestre\b|\btrimestre\s+actual\b|\beste\s+trim\b", re.IGNORECASE
)


def _corregir_trimestre_relativo(args: dict, task: str, hoy: date | None = None) -> bool:
    """Corrige «este/el trimestre» al trimestre ACTUAL (el 14B a veces pasa un trimestre específico
    equivocado, p.ej. 1T en junio). Solo toca referencias RELATIVAS de trimestre (no meses ni
    trimestres explícitos), así no rompe «junio» ni «2T 2026». Devuelve True si cambió el periodo.
    """
    if not _TRIMESTRE_RELATIVO.search(task or ""):
        return False
    actual = _trimestre_actual(hoy)
    if str(args.get("periodo") or "").strip() == actual:
        return False
    args["periodo"] = actual
    return True


# Preguntas de asesoramiento fiscal/legal REGULADO (¿qué IVA lleva mi actividad?, ¿estoy exento?,
# ¿puedo deducir?). El 14B inventa tipos/exenciones aunque le digas que no → garantizamos por CÓDIGO
# un aviso de "no es asesoramiento, confírmalo con tu gestor" (el modelo lo da de forma estocástica).
_FISCAL_REGULADO = re.compile(
    r"\btengo que (poner|ponerle|aplicar|cobrar|cargar|incluir)\w*[^.\n]{0,30}\biva\b"
    r"|\bqu[eé] (tipo de )?iva\b[^.\n]{0,30}(lleva|tiene|aplic\w+|pong|corresponde|debo|facturo)"
    r"|\b(estoy|est[aá]n?|estamos) exent|\bexenci[oó]n\b|\bexent[oa]s?\b"
    r"|\b(puedo|podr[ií]a) (deducir|desgravar)\b|\b(es|son) deducibles?\b"
    r"|\bme (deduzco|desgravo)\b|\bqu[eé] puedo (deducir|desgravar)\b",
    re.I,
)
_AVISO_REGULADO = (
    "⚠️ Esto es orientación general, NO asesoramiento fiscal: el tipo o la exención de IVA dependen de "
    "tu actividad y tienen matices, así que NO te lo doy como dato seguro. Confírmalo con tu gestor o "
    "en la AEAT antes de aplicarlo."
)


def _con_aviso_regulado(task: str, result: str) -> str:
    """Antepone un aviso determinista si la petición es fiscal/legal regulada. Garantiza la cautela
    que el 14B da de forma estocástica (y de-autoritativiza un tipo/exención que pueda haber inventado).
    """
    if not _FISCAL_REGULADO.search(task or ""):
        return result
    low = (result or "").lower()
    if "no asesoramiento fiscal" in low or ("asesoramiento" in low and "gestor" in low):
        return result  # ya lleva un aviso fuerte
    return _AVISO_REGULADO + ("\n\n" + result if result and result.strip() else "")


def _is_error_result(text: str) -> bool:
    """True si el texto es un resultado de error generado por el propio bucle al ejecutar una tool."""
    return bool(text) and text.startswith(_ERROR_PREFIXES)


def _error_brief(text: str, limit: int = 160) -> str:
    """Versión corta y legible (1 línea) de un resultado de error, para mensajes al modelo/usuario."""
    if not text:
        return ""
    linea = text.strip().splitlines()[0]
    return linea if len(linea) <= limit else linea[:limit] + "…"


# ── DoD (no mentir): no afirmar un éxito que no ocurrió ───────────────────────────────────────
# El 14B, ante una capacidad que NO tiene (p.ej. una minuta con retención de IRPF, no modelada),
# erraba registrar_factura y AUN ASÍ narraba «✅ Minuta preparada… 3450 €» (éxito + cifra inventada).
# Si se INTENTARON tools materiales y TODAS fallaron, el resultado no puede presentar un éxito.
_AFIRMA_EXITO_RX = re.compile(
    r"✅|\b(preparad[oa]s?|registrad[oa]s?|emitid[oa]s?|enviad[oa]s?|mandad[oa]s?|cread[oa]s?"
    r"|agendad[oa]s?|a[ñn]adid[oa]s?|completad[oa]s?|complet[eé]|generad[oa]s?|lista|listo|hecho)\b"
)
_NIEGA_EXITO_RX = re.compile(
    r"\bno\s+(he\s+podido|pude|puedo|se\s+(ha|han|pudo|puede)|es\s+posible|consig\w*|logr\w*|tengo)\b"
)
_MENSAJE_FALLO_HONESTO = (
    "No he podido completar esa acción: lo intenté pero la operación falló, así que no he "
    "registrado, enviado ni creado nada. No te doy por hecho algo que no se hizo. Dime si falta "
    "algún dato o si quieres que lo intente de otra forma."
)
# Tools con EFECTO real: su éxito = la acción que pidió el usuario OCURRIÓ (persistir/enviar/crear).
_TOOLS_EFECTO = ("registrar_factura", "gmail_send", "calendar_create")

# Retención de IRPF: hoy registrar_factura NO la modela. Registrar una factura con retención SIN la
# retención falsearía el 303 y el 111/130 → se rehúsa honesto (mejor «no lo hago» que hacerlo mal),
# hasta construir el modelo 130 (decisión de Fernando #8/#9). Lo destapó la presión del arnés: el 14B
# narraba «calculado el total con retención… preparando borrador» registrando una factura distorsionada.
# «reten\w+» cubre retención/retenido/retenida/retener (antes solo «retención» → «IRPF retenido» no
# casaba y la factura con retención no se rehusaba — destapado por la batería v2).
_RETENCION_IRPF = re.compile(r"\breten\w+\b", re.IGNORECASE)
_SIN_RETENCION = re.compile(
    r"\b(sin|no\s+(lleva|tiene|hay|aplica))\b[^.\n]{0,18}reten", re.IGNORECASE
)
_MSG_RETENCION_NO_MODELADA = (
    "⚠️ No he registrado la factura: lleva RETENCIÓN de IRPF y todavía no modelo la retención. "
    "Registrarla sin la retención falsearía tu 303 y tu 111/130, así que prefiero NO hacerlo a "
    "hacerlo mal. Apúntala con tu gestoría por ahora; cuando construyamos el modelo 130 la registro "
    "con su retención. (No se ha guardado nada.)"
)


def _lleva_retencion(task: str, args: dict) -> bool:
    """True si la factura a registrar lleva retención de IRPF (por el arg explícito o por el texto de
    la petición). «sin retención» NO cuenta. Conservador: ante retención, mejor rehusar que falsear.
    """
    r = (args or {}).get("retencion", (args or {}).get("retención"))
    if r not in (None, "", 0, "0", 0.0):
        try:
            return float(r) != 0
        except (ValueError, TypeError):
            return True
    t = task or ""
    if _SIN_RETENCION.search(t):
        return False
    return bool(_RETENCION_IRPF.search(t))


_HACER_FACTURA = re.compile(r"\b(minuta\w*|factura\w*)\b", re.IGNORECASE)
_VERBO_HACER = re.compile(
    r"\b(haz\w*|hacer|hag\w+|prepar\w+|reg[ií]str\w+|em[ií]t\w+|fact[uú]r\w+|ap[uú]nt\w+"
    r"|gener\w+|cre\w+)\b",
    re.IGNORECASE,
)


def _es_registro_con_retencion(task: str) -> bool:
    """True si la petición pide REGISTRAR/PREPARAR una factura o minuta CON retención de IRPF
    (capacidad no modelada). Excluye «sin retención» y las preguntas que no piden crear nada. Cubre
    TODOS los caminos por los que el 14B fabricaría (registrar_factura, mis-ruteo a calcular_303…),
    porque corta ANTES del ReAct."""
    t = task or ""
    if _SIN_RETENCION.search(t) or not _RETENCION_IRPF.search(t):
        return False
    return bool(_HACER_FACTURA.search(t) and _VERBO_HACER.search(t))


# IBAN inválido: no fabricamos un «✅ guardado» de un IBAN que no cuadra (longitud/checksum). El 14B
# lo aceptaba a ciegas (destapado por la batería v2). Validamos con `validar_iban` (mod-97) y rehusamos.
_IBAN_TOKEN = re.compile(r"\bES\s?\d[\d\s]{6,30}", re.IGNORECASE)
_GUARDA_IBAN = re.compile(
    r"\b(guarda\w*|gu[aá]rdame|apunta\w*|registra\w*|anota\w*|almacena\w*|gu[aá]rdalo)\b",
    re.IGNORECASE,
)
_MSG_IBAN_INVALIDO = (
    "⚠️ No he guardado ese IBAN: no es válido (no cuadra por longitud o dígito de control). Revísalo "
    "y pásamelo completo (un IBAN español tiene 24 caracteres) y lo guardo."
)


def _iban_invalido_a_guardar(task: str) -> bool:
    """True si la petición pide GUARDAR un IBAN y el IBAN del texto es INVÁLIDO (longitud/checksum)."""
    t = task or ""
    if "iban" not in t.lower() or not _GUARDA_IBAN.search(t):
        return False
    m = _IBAN_TOKEN.search(t)
    return bool(m) and not validar_iban(m.group(0))


# Modelos AEAT que Loombit NO calcula todavía (hoy solo el 303 de IVA). Pedir uno → abstención HONESTA
# (no confundirlo con el 303 pidiendo ventas/compras, ni fabricar un resultado). Construirlos = decisión
# de Fernando (#8/#9). El 303 NO entra aquí (sí se modela).
_MODELO_NO_MODELADO = re.compile(
    r"\bmodelo\s+(111|115|123|130|180|184|190|193|347|349|390)\b", re.IGNORECASE
)
_MSG_MODELO_NO_MODELADO = (
    "Todavía no calculo el modelo {m} — hoy Loombit prepara el 303 (IVA) desde tus facturas. Ese "
    "modelo lo lleva tu gestor; cuando lo construyamos, te lo preparo yo. Mientras, te ayudo con el "
    "303, registrar facturas o tus cobros."
)


def _modelo_no_modelado(task: str) -> str | None:
    """Devuelve el número del modelo AEAT pedido si NO está modelado (111/349/130…), o None."""
    m = _MODELO_NO_MODELADO.search(task or "")
    return m.group(1) if m else None


def _paso_es_fallo(step: object) -> bool:
    """True si el resultado del paso es un ERROR (de bucle o devuelto por la propia tool). Más
    liberal que `_is_error_result`: cualquier resultado que empiece por 'ERROR' cuenta como fallo.
    """
    r = (getattr(step, "result", "") or "").lstrip()
    return _is_error_result(r) or r.upper().startswith("ERROR")


def _afirma_exito(result: str) -> bool:
    """True si el texto AFIRMA haber completado una acción (✅ / 'preparada'/'enviado'/…) y NO admite
    a la vez que no pudo. Solo se usa cuando ya sabemos que toda acción material falló."""
    t = (result or "").lower()
    return bool(_AFIRMA_EXITO_RX.search(t)) and not _NIEGA_EXITO_RX.search(t)


def _consecutive_tool_errors(run: "AgentRun", tool_name: str) -> int:
    """Cuántas veces SEGUIDAS ha fallado `tool_name` (ignorando otras tools intercaladas). Se corta
    en cuanto esa tool tuvo un resultado no-error → mide flailing real, no fallos sueltos."""
    n = 0
    for s in reversed(run.steps):
        if s.tool_name != tool_name:
            continue
        if _is_error_result(s.result):
            n += 1
        else:
            break
    return n


def _inject_loop_hint(run: "AgentRun", incoming_calls: list) -> None:
    _LOOP_THRESHOLD = 3
    if not run.steps or not incoming_calls:
        return
    last_tools = [s.tool_name for s in run.steps[-_LOOP_THRESHOLD:]]
    if len(last_tools) < _LOOP_THRESHOLD:
        return
    if len(set(last_tools)) != 1:
        return
    repeated_tool = last_tools[0]
    if repeated_tool not in [tc.tool_name for tc in incoming_calls]:
        return
    hint = (
        f"[SISTEMA-ANTI-BUCLE]: Llevas {_LOOP_THRESHOLD} llamadas seguidas a "
        f"'{repeated_tool}' sin avanzar. Cambia de estrategia. "
        "Si la capacidad no existe llama propose_improvement y luego task_done."
    )
    run.messages.append({"role": "user", "content": hint})
    logger.warning("Bucle detectado: '%s' x%d run=%s", repeated_tool, _LOOP_THRESHOLD, run.id)


def _update_memory(run: "AgentRun") -> None:
    try:
        mem = get_memory()
        mem.extract_contacts_from_steps(run.steps)
        tools_used = list(dict.fromkeys(s.tool_name for s in run.steps))
        if run.result:
            mem.add_history(task=run.task, result=run.result, tools_used=tools_used, run_id=run.id)
        mem.extract_procedure_from_run(run)
    except Exception:
        pass
