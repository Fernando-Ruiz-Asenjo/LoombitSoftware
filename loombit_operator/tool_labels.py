"""
Capa de presentación HUMANA de las capacidades de Loombit.

El `tool_registry` usa nombres técnicos (`gmail_send`, `calendar_create`…) porque
los lee el LLM para decidir qué tool llamar. Pero cuando el usuario pregunta "¿qué
sabes hacer?", el operador NO debe soltar esos nombres técnicos: debe describir sus
capacidades en lenguaje humano, cálido y entendible.

Este módulo es la fuente de esa traducción: nombre técnico → etiqueta amigable. Lo
consume el prompt del agente (`agent/prompts.py`) y puede reusarse en la UI o en el
adaptador MCP (`annotations.title`). Es presentación pura: no cambia comportamiento.
"""

from __future__ import annotations

import re

# name técnico → (etiqueta amigable con emoji, descripción en lenguaje humano)
HUMAN_LABELS: dict[str, tuple[str, str]] = {
    # — Comunicación —
    "gmail_send": (
        "✉️ Enviar correos",
        "Redacto y envío tus correos por ti (tú apruebas antes de mandar).",
    ),
    "gmail_search": (
        "🔎 Buscar en tu correo",
        "Busco mensajes en tu bandeja para darte contexto o encontrar algo.",
    ),
    "contacts_find": (
        "👤 Encontrar contactos",
        "Busco el email de una persona en tu agenda de contactos.",
    ),
    # — Agenda —
    "calendar_create": ("📅 Crear eventos", "Te agendo citas y reuniones en tu calendario."),
    "calendar_today": ("🗓️ Ver tu día", "Miro qué tienes hoy en el calendario."),
    "daily_brief": (
        "☀️ Resumen del día",
        "Te preparo un resumen con lo importante de hoy: agenda, correos por responder y cobros que vencen.",
    ),
    # — Documentos y ficheros —
    "read_invoice": (
        "🧾 Leer facturas",
        "Leo una factura o albarán y saco sus datos (importe, fechas, IBAN…).",
    ),
    "read_file": ("📄 Leer documentos", "Abro y leo el contenido de un fichero tuyo."),
    "write_file": ("📝 Guardar documentos", "Creo o actualizo un fichero con lo que necesites."),
    "list_directory": ("📁 Explorar carpetas", "Miro qué hay en una carpeta."),
    # — Web —
    "web_fetch": ("🌐 Consultar la web", "Leo una página web para buscarte información."),
    # — Memoria —
    "memory_search": (
        "🧠 Recordar lo ya hecho",
        "Busco en tu histórico por significado (tareas, lecciones y empresas parecidas), no por palabra exacta.",
    ),
    # — Control de ordenador (Pilot) —
    "_desktop": (
        "🖥️ Manejar tu ordenador",
        "Cuando hace falta, manejo programas y webs por ti (banca, sede AEAT, facturación…), siempre a la vista y con tu permiso para cualquier paso con efecto.",
    ),
    # — Conversación —
    "ask_user": (
        "🙋 Preguntarte lo justo",
        "Solo te pregunto cuando me falta un dato que no puedo conseguir yo solo.",
    ),
}

# Tools internas/mecánicas del Pilot que NO se enumeran al usuario (las resume "_desktop").
_DESKTOP_PREFIXES = ("desktop_", "browser_")
_INTERNAL = {"task_done", "propose_improvement", "save_screenshot_to_file", "run_shell"}


# ── Saneador del texto que VE EL USUARIO ─────────────────────────────────────
# El prompt prohíbe nombrar tools, pero el 14B a veces lo incumple (y hasta alucina nombres como
# "calendar_search"). Garantía POR CÓDIGO (BRÚJULA: no fiarse solo del LLM): borra menciones de tools
# del texto de cara al usuario. Casa por PREFIJOS de tool (gmail_/calendar_/…) para no pisar nombres
# de fichero legítimos (mi_factura.pdf). Presentación pura: no cambia comportamiento del agente.
_TOOL_RE = re.compile(
    r"`?\b(?:gmail_\w+|calendar_\w+|contacts_\w+|daily_brief|memory_search|"
    r"read_invoice|read_file|write_file|list_directory|web_fetch|"
    r"desktop_\w+|browser_\w+|run_shell|ask_user|task_done|"
    r"propose_improvement|save_screenshot\w*)\b`?",
    re.IGNORECASE,
)
# Conector previo ("usando `x`", "mediante x", "llamando a x"…) para borrarlo junto con la tool.
_LEAD = (
    r"(?:usando|mediante|llamando a|vía|a trav[eé]s de|invocando|con la herramienta|"
    r"con la funci[oó]n|us[eé]|mediante la tool|con la tool)"
)


def humanize_user_text(text: str) -> str:
    """Quita menciones de tools del texto de cara al usuario (nunca debe ver jerga técnica)."""
    if not text:
        return text
    # 1) "…usando `calendar_search`…" → quita conector + tool de golpe.
    t = re.sub(rf"\s*\b{_LEAD}\b\s*{_TOOL_RE.pattern}", "", text, flags=re.IGNORECASE)
    # 2) cualquier mención suelta restante → fuera.
    t = _TOOL_RE.sub("", t)
    # 3) limpieza tipográfica (espacios dobles, espacio antes de signo, paréntesis vacíos).
    t = re.sub(r"\(\s*\)", "", t)
    t = re.sub(r"\s{2,}", " ", t)
    t = re.sub(r"\s+([,.;:）)])", r"\1", t)
    return t.strip()


# Señales de que el modelo escupió CÓDIGO/pseudocódigo como respuesta (fallo del 14B observado en
# vivo: a «¿qué reuniones tengo?» devolvió `for day in ...: print(...)`). El operador administrativo
# NUNCA debe contestar con código → si pasa, es basura y no se le enseña al usuario.
_CODE_SIGNS = re.compile(
    r"\bprint\(|\bfor\b[^\n]+\bin\b[^\n]+:|datetime\.now|\.strftime\(|\blambda\b|"
    r"\bdef\s+\w+\(|\bimport\s+\w+|=>|\}\s*;|sourceMapping|\w+\s*=\s*\w+\[",
    re.IGNORECASE,
)

_FALLBACK_BASURA = (
    "Me he liado resolviéndolo y no me ha salido limpio. ¿Lo reformulamos? "
    "Si quieres, te enseño tu agenda de hoy o el resumen del día."
)


def looks_like_code(text: str) -> bool:
    """True si el texto parece código/pseudocódigo en vez de una respuesta humana."""
    return bool(text) and bool(_CODE_SIGNS.search(text))


def safe_user_result(text: str) -> str:
    """Texto SEGURO de cara al usuario: sin jerga de tools y sin volcados de código.

    Si el modelo devolvió código/basura, se sustituye por un mensaje honesto con salida (BRÚJULA
    ley 9: nunca falles en silencio; mejor "no me salió" que un churro de código)."""
    clean = humanize_user_text(text)
    if looks_like_code(clean):
        return _FALLBACK_BASURA
    return clean


def human_label(name: str) -> str:
    """Etiqueta amigable para una tool (cae al propio nombre si no está mapeada)."""
    entry = HUMAN_LABELS.get(name)
    return entry[0] if entry else name


def capability_block() -> str:
    """Bloque de texto para el prompt: cómo describir las capacidades EN HUMANO.

    Enumera las capacidades de cara al usuario (sin las mecánicas internas del Pilot,
    que se resumen en una sola línea «manejar tu ordenador»)."""
    orden = [
        "daily_brief",
        "gmail_send",
        "gmail_search",
        "contacts_find",
        "calendar_today",
        "calendar_create",
        "read_invoice",
        "read_file",
        "write_file",
        "web_fetch",
        "memory_search",
        "_desktop",
    ]
    lineas = [f"  - {HUMAN_LABELS[n][0]}: {HUMAN_LABELS[n][1]}" for n in orden if n in HUMAN_LABELS]
    return "\n".join(lineas)
