"""
Skill W Pilot tools — el agente controla el escritorio completo.

Tools registradas (23 total):
  desktop_screenshot, desktop_read_screen, desktop_find,
  desktop_click, desktop_double_click, desktop_triple_click,
  desktop_mouse_move, desktop_drag, desktop_mouse_down, desktop_mouse_up,
  desktop_type, desktop_hotkey, desktop_scroll, desktop_navigate,
  desktop_wait, desktop_zoom, desktop_cursor_position,
  desktop_clipboard_read, desktop_clipboard_write, desktop_open_app,
  desktop_batch

Backend: POST /computer-use/*
Estado: parcial — funcional sin vision; zoom devuelve base64.
"""
from __future__ import annotations

import json
import os
from typing import Any

import httpx

from .registry import ToolDefinition, tool_registry

_BASE = os.environ.get("LOOMBIT_OPERATOR_URL", "http://127.0.0.1:8787")
_TIMEOUT = 20


def _cu_post(endpoint: str, payload: dict) -> str:
    try:
        r = httpx.post(f"{_BASE}/computer-use/{endpoint}", json=payload, timeout=_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        return data.get("result", json.dumps(data))
    except Exception as exc:
        return f"ERROR: {exc}"


def _cu_get(endpoint: str) -> str:
    try:
        r = httpx.get(f"{_BASE}/computer-use/{endpoint}", timeout=_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        return data.get("result", json.dumps(data))
    except Exception as exc:
        return f"ERROR: {exc}"


# Implementations

def _desktop_screenshot() -> str:
    result = _cu_post("screenshot", {})
    controls_raw = _cu_post("read_page", {})
    return f"PANTALLA: {result}\n\nCONTROLES VISIBLES:\n{controls_raw}"


def _desktop_read_screen(window_title: str = "") -> str:
    try:
        r = httpx.post(f"{_BASE}/computer-use/read_page", json={}, timeout=_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        result_text = data.get("result", "")
        window = data.get("window_title", "")
        count = data.get("controls_count", 0)
        return f"Ventana: '{window}' | {count} controles\n{result_text}"
    except Exception as exc:
        return f"ERROR: {exc}"


def _desktop_find(query: str) -> str:
    return _cu_post("find", {"query": query})


def _desktop_click(x: int, y: int, button: str = "left") -> str:
    return _cu_post("click", {"x": x, "y": y, "button": button})


def _desktop_double_click(x: int, y: int) -> str:
    return _cu_post("double_click", {"x": x, "y": y, "button": "left"})


def _desktop_triple_click(x: int, y: int) -> str:
    return _cu_post("triple_click", {"x": x, "y": y, "button": "left"})


def _desktop_mouse_move(x: int, y: int) -> str:
    return _cu_post("mouse_move", {"x": x, "y": y})


def _desktop_drag(x1: int, y1: int, x2: int, y2: int) -> str:
    return _cu_post("drag", {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "button": "left"})


def _desktop_mouse_down(x: int, y: int) -> str:
    return _cu_post("mouse_down", {"x": x, "y": y, "button": "left"})


def _desktop_mouse_up(x: int, y: int) -> str:
    return _cu_post("mouse_up", {"x": x, "y": y, "button": "left"})


def _desktop_wait(seconds: float = 1.0) -> str:
    return _cu_post("wait", {"seconds": min(float(seconds), 10.0)})


def _desktop_zoom(x0: int, y0: int, x1: int, y1: int) -> str:
    return _cu_post("zoom", {"x0": x0, "y0": y0, "x1": x1, "y1": y1})


def _desktop_cursor_position() -> str:
    return _cu_get("cursor_position")


def _desktop_clipboard_read() -> str:
    try:
        r = httpx.get(f"{_BASE}/computer-use/clipboard", timeout=_TIMEOUT)
        r.raise_for_status()
        data = r.json().get("result", {})
        if isinstance(data, dict):
            return data.get("clipboard", json.dumps(data))
        return str(data)
    except Exception as exc:
        return f"ERROR: {exc}"


def _desktop_clipboard_write(text: str) -> str:
    return _cu_post("clipboard", {"text": text})


def _desktop_open_app(app_name: str) -> str:
    return _cu_post("open_application", {"app_name": app_name})


def _desktop_batch(actions: list) -> str:
    return _cu_post("batch", {"actions": actions})


def _desktop_type(text: str) -> str:
    return _cu_post("type", {"text": text})


def _desktop_hotkey(keys: str) -> str:
    return _cu_post("key", {"key": keys})


def _desktop_scroll(x: int = 0, y: int = 0, direction: str = "down", amount: int = 3) -> str:
    return _cu_post("scroll", {"x": x, "y": y, "direction": direction, "amount": amount})


def _desktop_navigate(url: str) -> str:
    return _cu_post("navigate", {"url": url})


# Registry

tool_registry.register(ToolDefinition(
    name="desktop_screenshot",
    description=(
        "Captura el escritorio. Devuelve dimensiones, ruta de imagen y controles UI visibles. "
        "Usala al inicio de una tarea o para verificar el resultado de una accion."
    ),
    parameters={"type": "object", "properties": {}},
    fn=_desktop_screenshot,
    category="pilot",
))

tool_registry.register(ToolDefinition(
    name="desktop_read_screen",
    description=(
        "Lee la estructura de controles accesibles (botones, campos, menus) de la ventana activa. "
        "Devuelve tipos, nombres y posiciones. Mas preciso que screenshot para planear clics."
    ),
    parameters={
        "type": "object",
        "properties": {
            "window_title": {
                "type": "string",
                "description": "Titulo parcial de la ventana. Vacio = ventana activa.",
                "default": "",
            },
        },
    },
    fn=_desktop_read_screen,
    category="pilot",
))

tool_registry.register(ToolDefinition(
    name="desktop_find",
    description=(
        "Busca un elemento en pantalla por nombre/descripcion en lenguaje natural. "
        "Devuelve coordenadas del centro para usar con desktop_click."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Descripcion del elemento a encontrar."},
        },
        "required": ["query"],
    },
    fn=_desktop_find,
    category="pilot",
))

tool_registry.register(ToolDefinition(
    name="desktop_click",
    description="Hace clic en coordenadas absolutas de pantalla (pixeles). button: 'left' o 'right'.",
    parameters={
        "type": "object",
        "properties": {
            "x": {"type": "integer", "description": "Coordenada X en pixeles."},
            "y": {"type": "integer", "description": "Coordenada Y en pixeles."},
            "button": {"type": "string", "enum": ["left", "right"], "default": "left"},
        },
        "required": ["x", "y"],
    },
    fn=_desktop_click,
    category="pilot",
))

tool_registry.register(ToolDefinition(
    name="desktop_double_click",
    description="Doble clic en coordenadas absolutas. Para abrir ficheros o seleccionar palabra.",
    parameters={"type": "object", "properties": {
        "x": {"type": "integer"}, "y": {"type": "integer"},
    }, "required": ["x", "y"]},
    fn=_desktop_double_click, category="pilot",
))

tool_registry.register(ToolDefinition(
    name="desktop_triple_click",
    description="Triple clic para seleccionar toda la linea o campo de texto.",
    parameters={"type": "object", "properties": {
        "x": {"type": "integer"}, "y": {"type": "integer"},
    }, "required": ["x", "y"]},
    fn=_desktop_triple_click, category="pilot",
))

tool_registry.register(ToolDefinition(
    name="desktop_mouse_move",
    description="Mueve el cursor a (x,y) sin clic. Para hover states o tooltips.",
    parameters={"type": "object", "properties": {
        "x": {"type": "integer"}, "y": {"type": "integer"},
    }, "required": ["x", "y"]},
    fn=_desktop_mouse_move, category="pilot",
))

tool_registry.register(ToolDefinition(
    name="desktop_drag",
    description="Arrastra desde (x1,y1) hasta (x2,y2). Para sliders, ventanas, seleccion de texto.",
    parameters={"type": "object", "properties": {
        "x1": {"type": "integer"}, "y1": {"type": "integer"},
        "x2": {"type": "integer"}, "y2": {"type": "integer"},
    }, "required": ["x1", "y1", "x2", "y2"]},
    fn=_desktop_drag, category="pilot",
))

tool_registry.register(ToolDefinition(
    name="desktop_mouse_down",
    description="Pulsa el boton izquierdo en (x,y) sin soltarlo. Combinar con mouse_move + mouse_up.",
    parameters={"type": "object", "properties": {
        "x": {"type": "integer"}, "y": {"type": "integer"},
    }, "required": ["x", "y"]},
    fn=_desktop_mouse_down, category="pilot",
))

tool_registry.register(ToolDefinition(
    name="desktop_mouse_up",
    description="Suelta el boton izquierdo en (x,y). Usar tras desktop_mouse_down.",
    parameters={"type": "object", "properties": {
        "x": {"type": "integer"}, "y": {"type": "integer"},
    }, "required": ["x", "y"]},
    fn=_desktop_mouse_up, category="pilot",
))

tool_registry.register(ToolDefinition(
    name="desktop_type",
    description=(
        "Escribe texto con el teclado en el campo con foco. "
        "Da foco primero con desktop_click. Confirmar con desktop_hotkey('enter')."
    ),
    parameters={"type": "object", "properties": {
        "text": {"type": "string", "description": "Texto a escribir."},
    }, "required": ["text"]},
    fn=_desktop_type, category="pilot",
))

tool_registry.register(ToolDefinition(
    name="desktop_hotkey",
    description=(
        "Ejecuta combinacion de teclas. Ejemplos: 'enter', 'escape', 'ctrl+c', 'ctrl+v', "
        "'ctrl+a', 'win+r', 'alt+f4', 'win+d', 'ctrl+shift+esc'."
    ),
    parameters={"type": "object", "properties": {
        "keys": {"type": "string", "description": "Tecla o combinacion. Usa + para combinar."},
    }, "required": ["keys"]},
    fn=_desktop_hotkey, category="pilot",
))

tool_registry.register(ToolDefinition(
    name="desktop_scroll",
    description="Scroll del raton en (x,y). direction: 'down' o 'up'. amount: 1-10 (default 3).",
    parameters={"type": "object", "properties": {
        "direction": {"type": "string", "enum": ["up", "down"], "default": "down"},
        "amount": {"type": "integer", "default": 3},
        "x": {"type": "integer", "default": 0},
        "y": {"type": "integer", "default": 0},
    }},
    fn=_desktop_scroll, category="pilot",
))

tool_registry.register(ToolDefinition(
    name="desktop_navigate",
    description="Abre una URL en el navegador predeterminado del sistema.",
    parameters={"type": "object", "properties": {
        "url": {"type": "string", "description": "URL completa (https://...)."},
    }, "required": ["url"]},
    fn=_desktop_navigate, category="pilot",
))

tool_registry.register(ToolDefinition(
    name="desktop_wait",
    description="Espera N segundos (maximo 10). Para cargas de pagina o animaciones.",
    parameters={"type": "object", "properties": {
        "seconds": {"type": "number", "default": 1.0},
    }},
    fn=_desktop_wait, category="pilot",
))

tool_registry.register(ToolDefinition(
    name="desktop_zoom",
    description=(
        "Captura region rectangular (x0,y0)-(x1,y1) en detalle. "
        "Para leer texto pequenyo, inspeccionar botones o iconos."
    ),
    parameters={"type": "object", "properties": {
        "x0": {"type": "integer"}, "y0": {"type": "integer"},
        "x1": {"type": "integer"}, "y1": {"type": "integer"},
    }, "required": ["x0", "y0", "x1", "y1"]},
    fn=_desktop_zoom, category="pilot",
))

tool_registry.register(ToolDefinition(
    name="desktop_cursor_position",
    description="Devuelve la posicion actual del cursor del raton en pixeles (x, y).",
    parameters={"type": "object", "properties": {}},
    fn=_desktop_cursor_position, category="pilot",
))

tool_registry.register(ToolDefinition(
    name="desktop_clipboard_read",
    description="Lee el texto del portapapeles. Util tras Ctrl+C.",
    parameters={"type": "object", "properties": {}},
    fn=_desktop_clipboard_read, category="pilot",
))

tool_registry.register(ToolDefinition(
    name="desktop_clipboard_write",
    description="Escribe texto en el portapapeles. Despues usa desktop_hotkey('ctrl+v') para pegar.",
    parameters={"type": "object", "properties": {
        "text": {"type": "string"},
    }, "required": ["text"]},
    fn=_desktop_clipboard_write, category="pilot",
))

tool_registry.register(ToolDefinition(
    name="desktop_open_app",
    description=(
        "Lanza una aplicacion de Windows: 'notepad', 'calc', 'chrome', 'explorer', 'code', etc. "
        "Despues usa desktop_screenshot para confirmar."
    ),
    parameters={"type": "object", "properties": {
        "app_name": {"type": "string"},
    }, "required": ["app_name"]},
    fn=_desktop_open_app, category="pilot",
))

tool_registry.register(ToolDefinition(
    name="desktop_batch",
    description=(
        "Ejecuta una secuencia de acciones en un solo llamado sin round-trips extra. "
        "actions: lista de {action, params}. Se detiene en el primer error. "
        'Ejemplo: [{"action":"click","params":{"x":100,"y":200}},{"action":"type","params":{"text":"hola"}}]'
    ),
    parameters={"type": "object", "properties": {
        "actions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                    "params": {"type": "object"},
                },
                "required": ["action"],
            },
        },
    }, "required": ["actions"]},
    fn=_desktop_batch, category="pilot",
))
