"""
Tool Registry — catálogo de herramientas que el agente puede invocar.

Cada ToolDefinition tiene:
  - name:              identificador único (snake_case)
  - description:       qué hace (lo lee el LLM para decidir cuándo usarla)
  - parameters:        JSON Schema de los argumentos
  - fn:                función Python que ejecuta la tool
  - requires_approval: si True, el loop para y espera confirmación humana
  - safety_class:      passive | assisted | safety_sensitive | blocked_by_default

El método to_openai() convierte la definición al formato que espera la API
de LM Studio / OpenAI para function calling.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

# ── Activación de tools por intención (on-demand, no las 44 de golpe) ──────────
# Núcleo SIEMPRE disponible (control del bucle).
# La aprobación de efectos externos la fuerza el bucle sobre la tool real
# (requires_approval=True), no una tool aparte → una sola puerta, sin redundancia.
CORE_TOOLS: set[str] = {"task_done", "ask_user", "propose_improvement"}

# Grupos que se activan cuando la petición casa con sus palabras clave.
TOOL_GROUPS: list[tuple[tuple[str, ...], set[str]]] = [
    (
        (
            "correo",
            "email",
            "e-mail",
            "mail",
            "gmail",
            "envia",
            "envía",
            "manda",
            "remite",
            "escribe a",
            "responde a",
            "contesta",
            "destinatario",
            "buenas noches",
            "buenos dias",
        ),
        {"contacts_find", "gmail_search", "gmail_send"},
    ),
    (
        (
            "reunion",
            "reunión",
            "cita",
            "evento",
            "calendario",
            "agenda",
            "agéndame",
            "agendame",
            "convoca",
            "queda con",
            "videollamada",
        ),
        {"calendar_create", "contacts_find"},
    ),
    (
        ("busca correo", "buscar correo", "lee correo", "leer correo", "bandeja", "recibido"),
        {"gmail_search"},
    ),
    (
        (
            "histórico",
            "historico",
            "historial",
            "recuerda",
            "recuerdas",
            "ya hice",
            "ya hicimos",
            "la última vez",
            "la ultima vez",
            "parecido",
            "similar",
            "anteriormente",
            "qué sé de",
            "que se de",
        ),
        {"memory_search", "gmail_search"},
    ),
    (
        (
            "resumen",
            "resúmeme",
            "resumeme",
            "brief",
            "del día",
            "del dia",
            "de hoy",
            "qué tengo",
            "que tengo",
            "agenda",
            "foco",
            "cómo va",
            "como va",
            "en qué centrar",
            "en que centrar",
            "organiza mi día",
            "organiza mi dia",
        ),
        {"daily_brief", "calendar_today", "gmail_search"},
    ),
    (
        (
            "factura",
            "albaran",
            "albarán",
            "pdf",
            "documento",
            "cobro",
            "vencim",
            "iban",
            "importe",
            "extracto",
            "proveedor",
        ),
        {"read_invoice", "read_file", "list_directory"},
    ),
    (
        ("fichero", "archivo", "carpeta", "guarda", "directorio", "lee el", "escribe el"),
        {"read_file", "write_file", "list_directory"},
    ),
    (
        (
            "pantalla",
            "captura",
            "click",
            "clic",
            "ventana",
            "programa",
            "aplicacion",
            "aplicación",
            "abre",
            "escritorio",
            "excel",
            "navega",
            "web",
            "página",
            "pagina",
            "portal",
            "banco",
            "sede",
            "aeat",
            "whatsapp",
        ),
        {
            "desktop_screenshot",
            "desktop_ui_snapshot",
            "desktop_read_screen",
            "desktop_click",
            "desktop_click_accessibility",
            "desktop_type",
            "desktop_hotkey",
            "desktop_open_app",
            "desktop_navigate",
            "desktop_wait_for_window",
            "desktop_screen_changed",
        },
    ),
]

# Si la petición no casa con ningún grupo: set administrativo básico (API).
_DEFAULT_GROUP: set[str] = {"contacts_find", "gmail_search", "gmail_send", "calendar_create"}


def select_tool_names(task: str) -> set[str]:
    """Núcleo + los grupos cuya palabra clave aparece en la petición."""
    t = (task or "").lower()
    names = set(CORE_TOOLS)
    matched = False
    for keywords, group in TOOL_GROUPS:
        if any(k in t for k in keywords):
            names |= group
            matched = True
    if not matched:
        names |= _DEFAULT_GROUP
    return names


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema (type=object, properties, required)
    fn: Callable[..., Any]
    requires_approval: bool = False
    safety_class: str = "passive"  # passive | assisted | safety_sensitive
    category: str = "base"  # base | file | web | shell | connector | computer

    def to_openai(self) -> dict[str, Any]:
        """Formato que espera /chat/completions con tools."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def execute(self, **kwargs: Any) -> Any:
        return self.fn(**kwargs)

    def snapshot(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description[:80],
            "requires_approval": self.requires_approval,
            "safety_class": self.safety_class,
            "category": self.category,
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' ya está registrada")
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(f"Tool desconocida: '{name}'") from exc

    def list(self, category: str | None = None) -> list[ToolDefinition]:
        tools = list(self._tools.values())
        if category:
            tools = [t for t in tools if t.category == category]
        return sorted(tools, key=lambda t: t.name)

    def to_openai(
        self,
        category: str | None = None,
        profile: str | None = None,
        task: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Lista de tool definitions en formato OpenAI, lista para la API.

        Si se pasa `task`, se activan SOLO las tools que la petición requiere
        (núcleo + grupos por intención) — menos tokens, menor latencia y menos
        confusión del modelo. `category` filtra por categoría. `profile` se
        acepta por compatibilidad.
        """
        tools = self.list(category)
        if task is not None:
            allow = select_tool_names(task)
            tools = [t for t in tools if t.name in allow]
        return [t.to_openai() for t in tools]

    def snapshot(self) -> dict[str, Any]:
        tools = self.list()
        return {
            "count": len(tools),
            "tools": [t.snapshot() for t in tools],
        }


# Registro singleton — se popula en tools/base.py (y futuros módulos)
tool_registry = ToolRegistry()
