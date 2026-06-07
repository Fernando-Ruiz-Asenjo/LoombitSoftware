"""Tools — herramientas que el agente puede invocar."""
from .registry import ToolDefinition, ToolRegistry, tool_registry

# Registrar todas las tools al importar este módulo
from . import base      # noqa: F401 — read_file, write_file, list_directory, web_fetch, run_shell, task_done, request_approval
from . import computer  # noqa: F401 — browser_navigate, browser_click, browser_type, browser_key, browser_scroll, browser_screenshot, browser_read_page, browser_find
from . import pilot     # noqa: F401 — desktop_screenshot, desktop_read_screen, desktop_find, desktop_click, desktop_type, desktop_hotkey, desktop_scroll, desktop_navigate

__all__ = ["ToolDefinition", "ToolRegistry", "tool_registry"]
