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
from typing import Any

from ..llm import ChatResponse, LLMClient, ToolCall, tool_result_message
from ..tools import tool_registry
from ..tools.registry import ToolRegistry
from .memory import get_memory
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
        self, task: str, max_steps: int | None = None, profile: str = "administrativo"
    ) -> AgentRun:
        """Crea un AgentRun sin ejecutarlo — para lanzar en background."""
        run = self.store.create(task, max_steps=max_steps or self.max_steps)
        run.profile = profile
        # Pasar la tarea como hint para que la memoria incluya procedimientos relevantes
        memory_block = get_memory().to_context_block(task_hint=task)
        run.messages = [
            {"role": "system", "content": build_system_prompt(profile, memory_block)},
            {"role": "user", "content": task},
        ]
        self.store.save_run(run)
        return run

    def execute_run(self, run_id: str) -> AgentRun:
        """Ejecuta un run ya creado — seguro para llamar desde un thread."""
        run = self.store.get(run_id)
        return self._execute(run)

    def resume(self, run_id: str) -> AgentRun:
        """Reanuda un AgentRun en pending_approval tras recibir aprobación humana.

        Ejecuta la tool aprobada y reemplaza el placeholder PENDING_APPROVAL
        en el historial de mensajes con el resultado real antes de continuar.
        """
        run = self.store.get(run_id)
        if run.status != AgentStatus.PENDING_APPROVAL:
            raise ValueError(f"El run {run_id} no está en pending_approval (status={run.status})")

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

        run.approve()
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

    def answer(self, run_id: str, answer_text: str) -> AgentRun:
        """Inyecta la respuesta del usuario a una pregunta y reanuda el agente."""
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

        run.answer()
        self.store.save_run(run)

        # Guardar en memoria conversacional
        _log_conversation_event(run, "user_answer", answer_text)

        return self._execute(run)

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

        try:
            tools_schema = self.registry.to_openai(profile=run.profile, task=run.task)
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
                response: ChatResponse = self.llm.chat(
                    messages=run.messages,
                    tools=tools_schema,
                    tool_choice="auto",
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
                        run.mark_completed(content or "(sin resultado)")
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
                    run.mark_completed(done_summary)
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

    def _execute_tool_call(self, tc: ToolCall, step_num: int, run: AgentRun) -> tuple[str, bool]:
        try:
            tool_def = self.registry.get(tc.tool_name)
        except KeyError:
            return f"ERROR: tool desconocida '{tc.tool_name}'", False

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
        summary = str(args.get("summary", "")).strip()
        start = str(args.get("start_iso", "")).strip()
        return (
            "Crear un evento en tu calendario",
            f"Evento: {summary}\nInicio: {start}",
        )
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


def _is_error_result(text: str) -> bool:
    """True si el texto es un resultado de error generado por el propio bucle al ejecutar una tool."""
    return bool(text) and text.startswith(_ERROR_PREFIXES)


def _error_brief(text: str, limit: int = 160) -> str:
    """Versión corta y legible (1 línea) de un resultado de error, para mensajes al modelo/usuario."""
    if not text:
        return ""
    linea = text.strip().splitlines()[0]
    return linea if len(linea) <= limit else linea[:limit] + "…"


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
