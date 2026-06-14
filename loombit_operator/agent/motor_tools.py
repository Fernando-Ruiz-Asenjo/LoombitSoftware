"""
motor_tools.py — ejecución de una tool-call del agente (antes `AgentLoop._execute_tool_call`) + el
resume de lo aprobado, el anti-flailing y la reflexión de fallo.

Extraído de loop.py (en deuda de tamaño, >400; ratchet de la Brújula) SIN cambiar la lógica (`self.`
→ `loop.`), salvo el CABLEADO de D-96: la llamada a `AUTHORITY_PLANE.autorizar(...)` ahora pasa
`contenido_no_confiable=_contenido_no_confiable(run)` para que la cuarentena CaMeL actúe EN VIVO
(un argumento consecuente lifteado literal de un correo/web/documento leído → CORREGIR, no se ejecuta).
Importa de los módulos hoja (`correctores`, `salida`, `seguridad`) y colaboradores; nunca de `loop`.
"""

from __future__ import annotations

import json
import logging
import re

from ..llm import ToolCall
from ..policy.authority_plane import AUTHORITY_PLANE, Accion
from .correctores import (
    _corregir_fecha_calendario,
    _corregir_fecha_cobro,
    _corregir_importe,
    _corregir_periodo_303,
    _corregir_trimestre_relativo,
    _corregir_unidad_comparativa,
    _filtrar_lineas_303,
    _normalizar_alias_factura,
)
from . import memory
from .run import AgentRun
from .salida import (
    _SENTINEL_APPROVAL,
    _SENTINEL_QUESTION,
    _TOOL_ERROR_CUT,
    _consecutive_tool_errors,
    _describe_for_approval,
    _error_brief,
    _is_error_result,
)
from .seguridad import _contenido_no_confiable

logger = logging.getLogger(__name__)

# El asunto/cuerpo de un correo los redacta el agente, no el usuario. Si el modelo intenta
# preguntarlos vía ask_user, lo interceptamos y le devolvemos la orden de redactarlos él.
_PREGUNTA_AUTORREDACTABLE = re.compile(r"asunto|subject|cuerpo|\bbody\b|t[ií]tulo del correo", re.I)


def ejecutar_tool_call(loop, tc: ToolCall, step_num: int, run: AgentRun) -> tuple[str, bool]:
    try:
        tool_def = loop.registry.get(tc.tool_name)
    except KeyError:
        return f"ERROR: tool desconocida '{tc.tool_name}'", False

    # (La retención IRPF se rehúsa ya en la guarda de dominio pre-intent —ver registro_guardas—,
    # antes del ReAct, así que aquí no hace falta interceptarla por tool.)

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
    # D-4: la unidad de la comparativa (mes/trimestre/año) la fija el código desde el texto.
    if tc.tool_name == "resumen_comparativo" and _corregir_unidad_comparativa(
        tc.arguments, run.task
    ):
        logger.info("resumen_comparativo: unidad fijada desde el texto run=%s", run.id)
    # D-3: el 14B a veces nombra los args base_imponible/tipo_iva; la tool espera base/tipo.
    if tc.tool_name == "registrar_factura":
        _normalizar_alias_factura(tc.arguments)
    # D-3: importe-fiel — el 14B garbea la cifra al rellenar el arg (negativos, total-vs-base). Si
    # el texto tiene UN importe claro, lo recalcula el código (la brújula: «cifras por código»).
    if tc.tool_name in ("plan_cobro", "registrar_factura") and _corregir_importe(
        tc.tool_name, tc.arguments, run.task
    ):
        logger.info("%s: importe corregido desde el texto run=%s", tc.tool_name, run.id)

    # Señal visible PERSISTENTE: si el agente usa una tool de pilotaje (escritorio/navegador),
    # abre la sesión de halo → el usuario VE a Loombit pilotando durante todo el run.
    if tool_def.category in ("pilot", "computer"):
        from ..pilot import overlay_manager

        overlay_manager.start_session()

    # §GOB-1 — Capability Policy Plane: TODA la autoridad consecuente (gate de efecto, resolución
    # de destinatario, no-delatarse-bot, rehúsa ante manipulación) se decide en una superficie
    # ÚNICA. El LLM propuso la tool-call; el plano —código determinista— DISPONE. Ley Fundacional.
    # D-96 (CaMeL): le pasamos el contenido NO confiable leído en el run para que ponga en cuarentena
    # un argumento consecuente lifteado literal de un correo/web/documento (orden incrustada disfrazada
    # de dato) → CORREGIR, no se ejecuta a ciegas.
    decision = AUTHORITY_PLANE.autorizar(
        tool_name=tc.tool_name,
        arguments=tc.arguments,
        run=run,
        requires_approval=tool_def.requires_approval,
        contenido_no_confiable=_contenido_no_confiable(run),
    )
    if decision.accion in (Accion.CORREGIR, Accion.REHUSAR):
        logger.info(
            "§GOB-1 %s tool=%s run=%s (%s)",
            decision.accion.value,
            tc.tool_name,
            run.id,
            decision.motivo,
        )
        return decision.mensaje, False
    if decision.accion is Accion.APROBAR:
        reason, proposed = _describe_for_approval(tc.tool_name, tc.arguments)
        payload = json.dumps({"reason": reason, "proposed_action": proposed})
        return f"{_SENTINEL_APPROVAL}{payload}", True
    # Accion.EJECUTAR → adelante (cae al logger + tool_def.execute de abajo).

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
            logger.info("ask_user interceptado (asunto/cuerpo) — autocorrigiendo run=%s", run.id)
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
            # el resultado no es JSON (o no es dict): no es el caso "0 resultados" → se sigue con
            # el result_text original tal cual (sin añadir la pista). Tolerable, no rompe el flujo.
            pass

    return result_text, False


def maybe_cut_for_flailing(run: AgentRun, tool_calls: list[ToolCall]) -> str | None:
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


def resume_execute(loop, run_id: str) -> AgentRun:
    """Ejecuta la(s) tool(s) ya aprobada(s) y continúa el bucle. Asume que el run YA está en
    RUNNING (lo dejó `accept_approval`). Reemplaza cada placeholder PENDING_APPROVAL del
    historial por el resultado real antes de seguir."""
    run = loop.store.get(run_id)

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
            tool_def = loop.registry.get(pending_step.tool_name)
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
        detalle = "; ".join(f"«{s.tool_name}» → {_error_brief(s.result)}" for s in fallos_aprobados)
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
    loop.store.save_run(run)
    return loop._execute(run)


def aprender_de_fallo(loop, run: AgentRun) -> None:
    """Reflexión (sin fine-tuning): saca una lección general del fallo y la guarda en memoria.
    Best-effort — nunca rompe el run. La lección se recuperará en tareas futuras parecidas."""
    try:
        from .reflexion import etiquetas_de_tarea, reflexionar

        leccion = reflexionar(run, loop.llm)
        if leccion:
            memory.get_memory().add_lesson(
                leccion, tags=etiquetas_de_tarea(run.task), outcome="fallo", source="reflexion"
            )
            logger.info("Lección aprendida (run=%s): %s", run.id, leccion[:80])
    except Exception:
        logger.debug("aprender_de_fallo best-effort falló", exc_info=True)
