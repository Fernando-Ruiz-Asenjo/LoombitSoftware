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
        "_desktop",
    ]
    lineas = [f"  - {HUMAN_LABELS[n][0]}: {HUMAN_LABELS[n][1]}" for n in orden if n in HUMAN_LABELS]
    return "\n".join(lineas)
