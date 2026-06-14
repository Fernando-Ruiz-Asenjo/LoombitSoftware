"""
salida.py — sentinels, constantes compartidas y helpers de SALIDA del bucle del agente.

Extraído de loop.py (en deuda de tamaño, >400; ratchet de la Brújula) para poder cablear D-96 sin
engordarlo. Aquí viven: los sentinels que el bucle detecta en el resultado de las tools, los prefijos
de error, y los helpers que dan forma a lo que el usuario ve (tarjeta de aprobación, relay fiel de
cifras autoritativas, DoD «no afirmar un éxito que no ocurrió», avisos fiscales regulados, anti-bucle
y consolidación de memoria). Es la HOJA del grafo de módulos: no importa loop ni motor. Sin cambiar
comportamiento respecto a lo que vivía en loop.py.
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .run import AgentRun

logger = logging.getLogger(__name__)

# Sentinels detectados en el resultado de cualquier tool (mensajes NUESTROS, no datos externos).
_SENTINEL_DONE = "TASK_DONE:"
_SENTINEL_APPROVAL = "PENDING_APPROVAL:"
_SENTINEL_QUESTION = "PENDING_QUESTION:"

# Anti-flailing: si la MISMA tool falla esta cantidad de veces SEGUIDAS, el bucle corta en seco
# (no quema los 20 pasos martilleando algo roto). El 1er fallo solo avisa; el 2º detiene.
_TOOL_ERROR_CUT = 2

# Prefijos con los que el propio bucle marca un resultado como ERROR de ejecución de tool (tool
# inexistente, argumentos inválidos, excepción, o fallo al ejecutar lo ya aprobado). Se centralizan
# aquí para que productor (ejecutar_tool_call / resume) y detector (_is_error_result) no se
# desincronicen.
_ERROR_PREFIXES = (
    "ERROR: tool desconocida",
    "ERROR: argumentos invalidos",
    "ERROR en '",
    "ERROR al ejecutar",
)


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


# Contenido COMPUESTO no financiero (agenda/correo/tareas): si la narración lo menciona, aporta info
# que NO está en el bloque autoritativo (solo finanzas) → se conserva aunque sus cifras coincidan.
_CONTENIDO_COMPUESTO = re.compile(
    r"\b(reuni\w+|cita\w*|evento\w*|correo\w*|emails?|e-mails?|mensaje\w*|agenda\w*|"
    r"calendari\w+|tarea\w*|llamad\w+|recordatori\w+|plazo\w*|vencimiento\w*)\b",
    re.IGNORECASE,
)


def _parse_money(s: str) -> float | None:
    """Importe a float, tolerando formato es-ES (1.234,56) y en-US (1,234.56 / 2420.0). El ÚLTIMO
    separador con ≤2 dígitos detrás es el decimal; los demás son de miles."""
    s = s.strip().rstrip(".,")
    if "," in s and "." in s:
        s = (
            s.replace(".", "").replace(",", ".")
            if s.rfind(",") > s.rfind(".")
            else s.replace(",", "")
        )
    elif "," in s:
        ent, _, dec = s.rpartition(",")
        s = ent.replace(",", "") + "." + dec if len(dec) <= 2 else s.replace(",", "")
    elif "." in s:
        ent, _, dec = s.rpartition(".")
        s = ent.replace(".", "") + "." + dec if len(dec) <= 2 else s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def _importes_eur(texto: str) -> set[int]:
    """Importes en € del texto (parte entera redondeada): solo números pegados a €/euro(s), así un día
    o un «art. 8» o el «3» de «Ley 3/2004» NO cuentan como cifra. «2.420 €»/«2420.0 €»/«1.210,00 €» →
    {2420}/{2420}/{1210}."""
    out: set[int] = set()
    # El \b solo aplica a «eur(os)» (delimita la palabra); «€» no es carácter de palabra → un \b tras
    # él NUNCA casaría («2420 €.» / «40 €,») y se perdería todo importe escrito con el símbolo.
    for m in re.finditer(r"(\d[\d.,]*)\s*(?:€|eur(?:os?)?\b)", texto or "", re.IGNORECASE):
        val = _parse_money(m.group(1))
        if val is not None:
            out.add(round(val))
    return out


def _narracion_redundante(texto_llm: str, bloque_autoritativo: str) -> bool:
    """True si la narración del LLM solo RESTATEa los IMPORTES del bloque autoritativo (trae importes y
    TODOS están ya en el bloque, sin mencionar agenda/correo ni aportar un importe nuevo) → paráfrasis
    que duplicaría → se descarta. False si menciona contenido compuesto (agenda/correo) o trae un
    importe NUEVO → se conserva. Compara por VALOR en € (no por dígitos sueltos), así «2.420 €» =
    «2420.0 €» y el «3» de «3 correos» no cuenta como duplicado. Ver relay_fiel."""
    if _CONTENIDO_COMPUESTO.search(texto_llm or ""):
        return False
    imp = _importes_eur(texto_llm)
    return bool(imp) and not (imp - _importes_eur(bloque_autoritativo))


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
        from . import memory

        mem = memory.get_memory()
        mem.extract_contacts_from_steps(run.steps)
        tools_used = list(dict.fromkeys(s.tool_name for s in run.steps))
        if run.result:
            mem.add_history(task=run.task, result=run.result, tools_used=tools_used, run_id=run.id)
        mem.extract_procedure_from_run(run)
    except Exception:
        pass


# ── Composición de la salida final (relay fiel + DoD) ─────────────────────────────────────────────
def accion_fallida_sin_exito(run: "AgentRun") -> bool:
    """True si en el run se INTENTÓ alguna tool con EFECTO real (persistir/enviar/crear) y NINGUNA
    de ellas tuvo éxito (todas erraron) → la acción del usuario NO ocurrió, así que no se puede
    presentar un éxito. Solo cuentan las de efecto (no las de lectura: un 303-lectura «con éxito»
    sobre entidad vacía no significa que se registrara la factura que pedía el usuario)."""
    intentos = [s for s in run.steps if s.tool_name in _TOOLS_EFECTO]
    return bool(intentos) and all(_paso_es_fallo(s) for s in intentos)


def relay_fiel(loop, run: "AgentRun", result: str) -> str:
    """ALG-4.1 (relay fiel): garantiza que la salida VERBATIM de CADA tool AUTORITATIVA
    (cálculo determinista: cobro, 303, factura) está en el resultado, aunque el LLM la haya
    parafraseado. Así las cifras que ve el usuario == las que calculó el código. Recoge TODAS
    en orden (no solo la última): si se registran N facturas, el usuario ve las N, no una."""
    # DoD (no mentir): si toda acción material falló pero el texto afirma éxito, lo corregimos
    # por un mensaje honesto (no inventamos un «✅ hecho» que no ocurrió). Ver _afirma_exito.
    if accion_fallida_sin_exito(run) and _afirma_exito(result):
        return _con_aviso_regulado(getattr(run, "task", ""), _MENSAJE_FALLO_HONESTO)
    autoritativos: list[str] = []
    for s in run.steps:  # en ORDEN de ejecución
        try:
            td = loop.registry.get(s.tool_name)
        except Exception:
            continue
        if not getattr(td, "authoritative", False) or _is_error_result(s.result):
            continue
        verbatim = (s.result or "").strip()
        if verbatim and verbatim not in (result or "") and verbatim not in autoritativos:
            autoritativos.append(verbatim)
    if autoritativos:
        bloque = "\n\n".join(autoritativos)
        # El 14B suele PARAFRASEAR el bloque autoritativo en su narración final; mostrar AMBOS
        # duplica las cifras al usuario. Regla determinista: el bloque autoritativo SIEMPRE va; la
        # narración del LLM solo se añade si aporta alguna cifra NUEVA (respuesta COMPUESTA). Si
        # solo parafrasea las mismas cifras, se descarta → no se duplica.
        if result and result.strip() and not _narracion_redundante(result, bloque):
            result = bloque + "\n\n" + result
        else:
            result = bloque
    # Aviso determinista en preguntas fiscales reguladas (getattr: los tests pasan run sin .task).
    return _con_aviso_regulado(getattr(run, "task", ""), result)
