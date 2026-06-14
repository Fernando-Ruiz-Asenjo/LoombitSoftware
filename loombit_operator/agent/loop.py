"""
AgentLoop — motor ReAct (Reason + Act) de Loombit.

Ciclo:
  1. system_prompt + task → LLM
  2. LLM devuelve contenido (stop) o tool_calls
  3. Si stop            → ¿es TASK_DONE? → terminar | si no, seguir
  4. Si tool_calls      → ejecutar cada tool → añadir resultados → volver a 2
  5. Si PENDING_APPROVAL en cualquier resultado → pausar
  6. Si exceeded_max_steps → marcar como failed

El CUERPO del bucle (antes `_execute`/`_execute_tool_call`) vive en `motor_loop`/`motor_tools`: esta
clase deja wrappers finos que delegan. Los helpers deterministas viven en `salida`/`seguridad`/
`correctores`. Así loop.py se mantiene < 400 líneas (ratchet de la Brújula). Los símbolos privados que
importan `policy.authority_plane`, `fabrica.gepa*` y los tests se RE-EXPORTAN aquí (idiom `X as X`,
re-export intencional) para no romper esos importadores tras la descomposición.
"""

from __future__ import annotations

import logging

from ..llm import LLMClient, ToolCall
from ..tools import tool_registry
from ..tools.registry import ToolRegistry
from . import memory, motor_loop, motor_tools, salida
from .prompts import build_system_prompt
from .run import AgentRun, AgentStatus, AgentStore

# ── Re-exports de compatibilidad (idiom `X as X` = re-export intencional, sin F401) ───────────────
from .correctores import (
    _corregir_fecha_calendario as _corregir_fecha_calendario,
    _corregir_fecha_cobro as _corregir_fecha_cobro,
    _corregir_importe as _corregir_importe,
    _corregir_periodo_303 as _corregir_periodo_303,
    _corregir_unidad_comparativa as _corregir_unidad_comparativa,
    _filtrar_lineas_303 as _filtrar_lineas_303,
    _normalizar_alias_factura as _normalizar_alias_factura,
    _trimestre_actual as _trimestre_actual,
)
from .motor_loop import _texto_para_intencion as _texto_para_intencion
from .salida import (
    _SENTINEL_APPROVAL as _SENTINEL_APPROVAL,
    _SENTINEL_DONE as _SENTINEL_DONE,
    _SENTINEL_QUESTION as _SENTINEL_QUESTION,
    _con_aviso_regulado as _con_aviso_regulado,
    _consecutive_tool_errors as _consecutive_tool_errors,
    _describe_for_approval as _describe_for_approval,
    _error_brief as _error_brief,
    _is_error_result as _is_error_result,
    _log_conversation_event as _log_conversation_event,
    _narracion_redundante as _narracion_redundante,
    _strip_tool_artifacts as _strip_tool_artifacts,
)
from .seguridad import (
    _DELATA_BOT as _DELATA_BOT,
    _MANIPULACION as _MANIPULACION,
    _MSG_MANIPULACION as _MSG_MANIPULACION,
    _blindar_tool_results as _blindar_tool_results,
    _destinatario_claro as _destinatario_claro,
    _intento_manipulacion as _intento_manipulacion,
    _recipiente_resuelto as _recipiente_resuelto,
    _sanear_dato_no_confiable as _sanear_dato_no_confiable,
)

logger = logging.getLogger(__name__)


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
        memory_block = memory.get_memory().to_context_block(task_hint=task)
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

    # ── Motor interno → wrappers finos que delegan en motor_loop / motor_tools ──
    # (La lógica se extrajo a esos módulos para mantener loop.py < 400; el comportamiento es idéntico.)

    def _execute(self, run: AgentRun) -> AgentRun:
        return motor_loop.ejecutar(self, run)

    def _resume_execute(self, run_id: str) -> AgentRun:
        return motor_tools.resume_execute(self, run_id)

    def _intentar_multi_intent(self, run: AgentRun) -> bool:
        return motor_loop.intentar_multi_intent(self, run)

    def _accion_fallida_sin_exito(self, run: AgentRun) -> bool:
        return salida.accion_fallida_sin_exito(run)

    def _relay_fiel(self, run: AgentRun, result: str) -> str:
        return salida.relay_fiel(self, run, result)

    def _execute_tool_call(self, tc: ToolCall, step_num: int, run: AgentRun) -> tuple[str, bool]:
        return motor_tools.ejecutar_tool_call(self, tc, step_num, run)

    def _maybe_cut_for_flailing(self, run: AgentRun, tool_calls: list[ToolCall]) -> str | None:
        return motor_tools.maybe_cut_for_flailing(run, tool_calls)

    def _aprender_de_fallo(self, run: AgentRun) -> None:
        return motor_tools.aprender_de_fallo(self, run)
