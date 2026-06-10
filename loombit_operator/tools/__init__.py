"""Tools — herramientas que el agente puede invocar."""

from .registry import ToolDefinition, ToolRegistry, tool_registry

# Registrar todas las tools al importar este módulo
from . import base  # noqa: F401
from . import computer  # noqa: F401
from . import pilot  # noqa: F401
from . import documents  # noqa: F401
from . import connectors  # noqa: F401  (gmail_send, gmail_search, calendar_create, contacts_find)
from . import brief  # noqa: F401  (daily_brief, calendar_today — percepción del día)
from . import dominio  # noqa: F401  (plan_cobro, calcular_303 — cerebros admin como tools)
from . import conciliacion_tool  # noqa: F401  (conciliar_banco — extracto N43 vs cobros)

__all__ = ["ToolDefinition", "ToolRegistry", "tool_registry"]
