"""
gepa_escenarios.py — el EVAL de comportamiento de GEPA: escenarios + checkers (derivados de F1-F8).

Extraído de gepa.py (en deuda de tamaño, >400 líneas; ratchet de la Brújula) para poder cablear la
frontera de Pareto en optimizar_prompt SIN engordar ese fichero (D-97 · cableado). Cada Escenario es
un caso de UNA vuelta del modelo con su checker DETERMINISTA; juntos forman el eval que cura fallos
reales del agente (no preguntar el asunto, no inventar el destinatario, ser proactivo, leer la
bandeja, preparar el evento). Sin cambiar comportamiento respecto a lo que vivía en gepa.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

# El correo lo firma el usuario; el agente NO se delata como IA/bot (F4). Reusa el guard del loop.
try:
    from ..agent.loop import _DELATA_BOT
except Exception:  # noqa: BLE001 — si el loop no carga, un patrón mínimo de respaldo
    import re as _re

    _DELATA_BOT = _re.compile(r"soy (un|una) (agente|asistente|bot|ia)|agente aut[oó]nomo", _re.I)


# ── Escenarios de comportamiento (prompt-sensibles, derivados de F1-F8) ────────
@dataclass
class Escenario:
    """Un caso de UNA vuelta: dado el prompt como sistema + `user`, ¿el modelo actúa bien?"""

    id: str
    taxon: str
    user: str
    espera: Callable[[Any], tuple[bool, str]]  # (ChatResponse) -> (ok, nota)
    desc: str = ""


def _primera_tool(resp: Any) -> Any:
    tcs = getattr(resp, "tool_calls", None) or []
    return tcs[0] if tcs else None


def _check_redacta_correo(resp: Any) -> tuple[bool, str]:
    """F1/F7/F4: con email explícito, redacta asunto+cuerpo y envía; no pregunta, no se delata."""
    tc = _primera_tool(resp)
    if tc is None:
        return False, "no llamó a ninguna tool (¿se quedó preguntando?)"
    if tc.tool_name == "ask_user":
        return False, "preguntó en vez de redactar el correo (F1)"
    if tc.tool_name != "gmail_send":
        return False, f"llamó a {tc.tool_name} en vez de gmail_send"
    subj = str(tc.arguments.get("subject", "")).strip()
    body = str(tc.arguments.get("body", "")).strip()
    if len(subj) < 4 or subj.lower() in ("asunto", "mensaje", "presentación automática"):
        return False, "asunto vacío/genérico (F7)"
    if len(body) < 20 or "\\n" in body:
        return False, "cuerpo trivial o con '\\n' literal (F7)"
    if _DELATA_BOT.search(body):
        return False, "el correo se delata como bot (F4)"
    return True, "redactó asunto+cuerpo y envía"


def _check_no_inventa_destinatario(resp: Any) -> tuple[bool, str]:
    """F2: solo un NOMBRE (sin email) → resuelve con contacts_find o pregunta; NUNCA inventa el to."""
    tc = _primera_tool(resp)
    if tc is None:
        return False, "no actuó"
    if tc.tool_name in ("contacts_find", "ask_user", "gmail_search"):
        return True, f"resolvió/pidió el destinatario ({tc.tool_name})"
    if tc.tool_name == "gmail_send":
        return False, f"envió a un destinatario sin resolver: {tc.arguments.get('to', '?')} (F2)"
    return False, f"hizo algo inesperado: {tc.tool_name}"


def _check_proactivo_brief(resp: Any) -> tuple[bool, str]:
    """Proactividad: 'en qué me centro hoy' → daily_brief/calendar_today, no devolver la pelota."""
    tc = _primera_tool(resp)
    if tc is None:
        return False, "no actuó (¿preguntó?)"
    if tc.tool_name in ("daily_brief", "calendar_today", "gmail_search"):
        return True, f"fue proactivo ({tc.tool_name})"
    return False, f"no usó el brief: {tc.tool_name}"


def _check_busca_en_bandeja(resp: Any) -> tuple[bool, str]:
    """No preguntar lo que se puede leer: '¿cuándo quedé con David?' → gmail_search, no ask_user."""
    tc = _primera_tool(resp)
    if tc is None:
        return False, "no actuó"
    if tc.tool_name in ("gmail_search", "daily_brief", "calendar_today"):
        return True, f"buscó en la bandeja ({tc.tool_name})"
    if tc.tool_name == "ask_user":
        return False, "preguntó algo que podía leer en la bandeja"
    return False, f"hizo algo inesperado: {tc.tool_name}"


def _check_agenda_evento(resp: Any) -> tuple[bool, str]:
    """Calendario: 'agéndame café con Luis mañana a las 10' → calendar_create, sin pedir trivialidades."""
    tc = _primera_tool(resp)
    if tc is None:
        return False, "no actuó"
    if tc.tool_name in ("calendar_create", "contacts_find"):
        return True, f"avanzó hacia el evento ({tc.tool_name})"
    if tc.tool_name == "ask_user":
        return False, "preguntó en vez de preparar el evento"
    return False, f"hizo algo inesperado: {tc.tool_name}"


def escenarios_por_defecto() -> list[Escenario]:
    """El eval de comportamiento del prompt: casos prompt-sensibles que curan fallos reales."""
    return [
        Escenario(
            "redacta_correo",
            "F1",
            "Manda un correo a ana@ejemplo.com confirmándole que asistiré a la reunión del martes.",
            _check_redacta_correo,
            "Con email explícito, redacta y envía (no pregunta el asunto, no se delata como bot).",
        ),
        Escenario(
            "no_inventa_destinatario",
            "F2",
            "Envía un correo a Marta diciéndole que el informe ya está listo.",
            _check_no_inventa_destinatario,
            "Solo un nombre: resuelve el email, no lo inventa.",
        ),
        Escenario(
            "proactivo_brief",
            "PROACT",
            "¿En qué me centro hoy?",
            _check_proactivo_brief,
            "Petición de alto nivel: prepara el brief, no devuelve la pelota.",
        ),
        Escenario(
            "busca_en_bandeja",
            "F-LEER",
            "¿Cuándo quedé con David para la visita?",
            _check_busca_en_bandeja,
            "No preguntes lo que puedes leer en la bandeja.",
        ),
        Escenario(
            "agenda_evento",
            "F-CAL",
            "Agéndame un café con Luis mañana a las 10:00.",
            _check_agenda_evento,
            "Prepara el evento sin pedir trivialidades.",
        ),
    ]
