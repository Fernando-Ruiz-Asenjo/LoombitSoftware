"""Tools — herramientas que el agente puede invocar."""

from .registry import ToolDefinition, ToolRegistry, tool_registry

# Registrar todas las tools al importar este módulo
from . import base  # noqa: F401
from . import computer  # noqa: F401
from . import pilot  # noqa: F401

__all__ = ["ToolDefinition", "ToolRegistry", "tool_registry"]
