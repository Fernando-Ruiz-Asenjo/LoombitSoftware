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
from typing import Any

from ..llm import ChatResponse, LLMClient, ToolCall, tool_result_message
from ..tools import tool_registry
from ..tools.registry import ToolRegistry
from .prompts import build_system_prompt
from .run import AgentRun, AgentStatus, AgentStep, AgentStore

logger = logging.getLogger(__name__)

_SENTINEL_DONE     = "TASK_DONE:"
_SENTINEL_APPROVAL = "PENDING_APPROVAL:"


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
        self.llm      = llm      or LLMClient()
        self.registry = registry or tool_registry
        self.store    = store    or AgentStore()
        self.max_steps = max_steps

    # ── API pública ───────────────────────────────────────────────────────────

    def run(self, task: str) -> AgentRun:
        """Crea un AgentRun nuevo y ejecuta el bucle hasta completar o pausar."""
        agent_run = self.store.create(task, max_steps=self.max_steps)
        return self._execute(agent_run)

    def resume(self, run_id: str) -> AgentRun:
        """Reanuda un AgentRun en pending_approval tras recibir aprobación humana."""
        agent_run = self.store.get(run_id)
        if agent_run.status != AgentStatus.PENDING_APPROVAL:
            raise ValueError(
                f"El run {run_id} no está en pending_approval (status={agent_run.status})"
            )
        agent_run.approve()
        self.store.save_run(agent_run)
        return self._execute(agent_run)

    # ── Motor interno ─────────────────────────────────────────────────────────

    def _execute(self, run: AgentRun) -> AgentRun:
        run.mark_running()
        self.store.save_run(run)

        # Primer mensaje si es un run nuevo (sin historial)
        if not run.messages:
            run.messages = [
                {"role": "system", "content": build_system_prompt()},
                {"role": "user",   "content": run.task},
            ]

        tools_schema = self.registry.to_openai()

        try:
            while True:
                # Guard: límite de pasos
                if run.exceeded_max_steps:
                    run.mark_failed(
                        f"Límite de {run.max_steps} pasos alcanzado sin completar la tarea."
                    )
                    self.store.save_run(run)
                    return run

                # ── Llamar al LLM ──────────────────────────────────────────────
                logger.debug(
                    "AgentLoop step=%d run=%s messages=%d",
                    run.step_count, run.id, len(run.messages),
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
                    content = response.content.strip()

                    # Puede que devuelva el sentinel en texto plano
                    done_result = _extract_sentinel(content, _SENTINEL_DONE)
                    if done_result is not None:
                        run.mark_completed(done_result)
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
                        self.store.save_run(run)
                        return run

                    # finish_reason=length u otro: continuar el bucle
                    self.store.save_run(run)
                    continue

                # ── Caso: el LLM quiere ejecutar tools ────────────────────────
                tool_results: list[dict] = []
                pending_approval: dict | None = None

                for tc in response.tool_calls:
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

                    if needs_stop and pending_approval is None:
                        parsed = _parse_approval_json(
                            result_text[len(_SENTINEL_APPROVAL):]
                            if result_text.startswith(_SENTINEL_APPROVAL)
                            else result_text
                        )
                        pending_approval = {
                            "reason":          parsed.get("reason", "Aprobación requerida"),
                            "proposed_action": parsed.get("proposed_action", result_text),
                            "tool_call_id":    tc.id,
                        }

                # Añadir resultados de tools al historial
                run.messages.extend(tool_results)

                # Verificar sentineles en los resultados de tools
                done_summary = _first_sentinel(
                    [tr["content"] for tr in tool_results], _SENTINEL_DONE
                )
                if done_summary is not None:
                    run.mark_completed(done_summary)
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

                # Ningún sentinel → seguir el bucle
                self.store.save_run(run)

        except Exception as exc:
            logger.exception("AgentLoop error en run=%s", run.id)
            run.mark_failed(f"Error inesperado: {exc}")
            self.store.save_run(run)
            return run

    def _execute_tool_call(
        self, tc: ToolCall, step_num: int, run: AgentRun
    ) -> tuple[str, bool]:
        """
        Ejecuta una tool call.
        Devuelve (result_text, needs_stop).
        needs_stop=True si la tool tiene requires_approval=True o devuelve PENDING_APPROVAL.
        """
        try:
            tool_def = self.registry.get(tc.tool_name)
        except KeyError:
            return f"ERROR: tool desconocida '{tc.tool_name}'", False

        # Tools que requieren aprobación antes de ejecutarse → detener el loop
        if tool_def.requires_approval:
            # En vez de ejecutar, devolvemos un PENDING_APPROVAL automático
            payload = json.dumps({
                "reason": f"La tool '{tc.tool_name}' requiere aprobación antes de ejecutarse.",
                "proposed_action": (
                    f"Ejecutar {tc.tool_name} con argumentos: {json.dumps(tc.arguments, ensure_ascii=False)}"
                ),
            })
            return f"{_SENTINEL_APPROVAL}{payload}", True

        logger.info("Ejecutando tool '%s' step=%d run=%s", tc.tool_name, step_num, run.id)
        try:
            result = tool_def.execute(**tc.arguments)
        except TypeError as exc:
            return f"ERROR: argumentos inválidos para '{tc.tool_name}': {exc}", False
        except Exception as exc:
            return f"ERROR en '{tc.tool_name}': {exc}", False

        result_text = str(result)

        # La tool puede devolver sentineles directamente
        if result_text.startswith(_SENTINEL_APPROVAL):
            return result_text, True

        return result_text, False


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_sentinel(text: str, prefix: str) -> str | None:
    """Extrae el payload tras un sentinel si está presente."""
    if text.startswith(prefix):
        return text[len(prefix):]
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
        return {"reason": payload, "proposed_action": payload}
