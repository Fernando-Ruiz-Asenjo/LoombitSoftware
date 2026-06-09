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

# Reach admin SIEMPRE disponible: el agente NUNCA debe estar ciego a su correo, su agenda,
# sus contactos, su memoria, la web ni a leer un documento. Son las manos del oficio. Antes
# se ocultaban tras palabras clave frágiles → el vocabulario de medio oficio (p.ej. "vuelo",
# "hotel", "viaje") no casaba con nada y el agente se quedaba solo con correo+calendario,
# diciendo "no tengo capacidad para abrir webs" cuando SÍ tiene web_fetch. Esto es el piso.
ADMIN_BASE: set[str] = {
    "gmail_search",
    "gmail_send",
    "contacts_find",
    "calendar_create",
    "calendar_today",
    "memory_search",
    "web_fetch",
    "read_invoice",
}

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
            "factúrale",
            "facturale",
            "emite",
            "emitir",
            "emíteme",
            "apunta",
            "registra",
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
        {"registrar_factura", "read_invoice", "read_file", "list_directory"},
    ),
    (
        ("fichero", "archivo", "carpeta", "guarda", "directorio", "lee el", "escribe el"),
        {"read_file", "write_file", "list_directory"},
    ),
    (
        (
            "cobro",
            "cobrar",
            "reclama",
            "reclamar",
            "reclamación",
            "reclamacion",
            "moroso",
            "morosidad",
            "impago",
            "impagad",
            "deuda",
            "vencida",
            "vencimiento",
            "pendiente de pago",
            "demora",
        ),
        {"plan_cobro", "gmail_search", "gmail_send"},
    ),
    (
        (
            "303",
            "iva",
            "trimestre",
            "trimestral",
            "modelo 303",
            "liquidación",
            "liquidacion",
            "declaración",
            "declaracion",
            "hacienda",
            "devengado",
            "soportado",
            "repercutido",
        ),
        {"calcular_303", "calcular_303_registradas", "read_invoice"},
    ),
    (
        (
            "vuelo",
            "vuelos",
            "viaje",
            "viajar",
            "hotel",
            "hoteles",
            "alojamiento",
            "reserva",
            "reservar",
            "billete",
            "booking",
            "escapada",
            "crucero",
            "ida y vuelta",
            "alquiler de coche",
        ),
        # El motor de viajes es el PILOT: el agente OPERA un sitio real (no una API),
        # busca y deja la reserva preparada hasta el pago (gate). Le damos sus manos.
        {
            "browser_navigate",
            "browser_read_page",
            "browser_find",
            "browser_click",
            "browser_type",
            "browser_key",
            "browser_scroll",
            "browser_screenshot",
            "web_fetch",
        },
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


def select_tool_names(task: str) -> set[str]:
    """Piso robusto (núcleo + reach admin) + los grupos especialistas cuya palabra clave aparece.

    Antes: si la petición no casaba con ninguna keyword, el agente se quedaba solo con
    correo+calendario y quedaba CIEGO a la web, la memoria y los documentos que sí tiene.
    Ahora el reach admin (`ADMIN_BASE`) está SIEMPRE disponible; los grupos especialistas
    (ficheros, escritorio/Pilot, etc.) se añaden encima por intención. ~11-15 tools, dentro
    de lo que el 14B maneja sin confundirse, y sin manos atadas.
    """
    t = (task or "").lower()
    names = set(CORE_TOOLS) | set(ADMIN_BASE)
    for keywords, group in TOOL_GROUPS:
        if any(k in t for k in keywords):
            names |= group
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
    # ALG-4.1 (relay fiel): si True, su resultado es AUTORITATIVO (cálculo determinista) y debe
    # mostrarse VERBATIM al usuario; el LLM no debe parafrasear sus cifras. Lo garantiza el bucle.
    authoritative: bool = False

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
