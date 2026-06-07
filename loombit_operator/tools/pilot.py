"""
Skill W Pilot tools — el agente controla el escritorio completo.

Estas tools permiten al agente de Loombit ver y controlar el escritorio
de forma autónoma, usando Skill W Loombit Pilot como backend.

  desktop_screenshot   — captura de pantalla; devuelve estado visual + controles
  desktop_read_screen  — enumera los controles UI de la ventana activa
  desktop_find         — busca un elemento en pantalla por nombre/descripción
  desktop_click        — clic en coordenadas absolutas de pantalla
  desktop_type         — escribe texto con el teclado
  desktop_hotkey       — combinación de teclas (ctrl+c, alt+f4, win+r, etc.)
  desktop_scroll       — scroll en coordenadas
  desktop_navigate     — abre una URL en el navegador del sistema

Backend: POST /loombit/pilot/execute o /computer-use/*
Estado: 🟠 parcial — funcional con pywinauto; vision (imagen real) pendiente.

Diferencia con browser_* tools:
  - browser_* asumen que el objetivo es Chrome/web
  - desktop_* controlan cualquier app Windows nativa
"""
from __future__ import annotations

import json
import os
from typing import Any

import httpx

from .registry import ToolDefinition, tool_registry

_BASE = os.environ.get("LOOMBIT_OPERATOR_URL", "http://127.0.0.1:8787")
_TIMEOUT = 20


def _pilot_step(step: dict) -> dict:
    """Ejecuta un único paso en el Pilot y devuelve el resultado del paso."""
    try:
        r = httpx.post(
            f"{_BASE}/loombit/pilot/execute",
            json={
                "objective": step.get("type", "step"),
                "steps": [step],
                "dry_run": False,
                "operator_command": "agent_tool",
            },
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        results = data.get("steps_results", [])
        if results:
            first = results[0]
            if first.get("error"):
                return {"error": first["error"]}
            return first.get("result", first)
        return data
    except httpx.ConnectError:
        return {"error": "No se pudo conectar al operador Loombit en :8787"}
    except Exception as exc:
        return {"error": str(exc)}


def _cu_post(endpoint: str, payload: dict) -> str:
    """Llama al endpoint /computer-use/ y devuelve texto."""
    try:
        r = httpx.post(f"{_BASE}/computer-use/{endpoint}", json=payload, timeout=_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        return data.get("result", json.dumps(data))
    except Exception as exc:
        return f"ERROR: {exc}"


# ── Implementaciones ──────────────────────────────────────────────────────────

def _desktop_screenshot() -> str:
    """
    Captura el escritorio y devuelve:
      - Dimensiones de pantalla
      - Ruta donde se guardó la imagen
      - Lista de controles UI de la ventana en primer plano
    Esto permite al agente entender el estado actual de la pantalla.
    """
    result = _cu_post("screenshot", {})
    # Complementar con los controles de la ventana activa
    controls_raw = _cu_post("read_page", {})
    # Construir una representación textual compacta del estado de pantalla
    return (
        f"PANTALLA: {result}\n\n"
        f"CONTROLES VISIBLES:\n{controls_raw}"
    )


def _desktop_read_screen(window_title: str = "") -> str:
    """
    Lee y devuelve los controles accesibles de la ventana indicada (o la activa).
    Cada control indica tipo, nombre y posición aproximada.
    Útil para planear dónde hacer clic.
    """
    r = httpx.post(
        f"{_BASE}/computer-use/read_page",
        json={},
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    data = r.json()
    result_text = data.get("result", "")
    window = data.get("window_title", "")
    count = data.get("controls_count", 0)
    return f"Ventana: '{window}' | {count} controles\n{result_text}"


def _desktop_find(query: str) -> str:
    """
    Busca un elemento en la pantalla por nombre o descripción en lenguaje natural.
    Devuelve el elemento encontrado y sus coordenadas del centro para hacer clic.
    """
    return _cu_post("find", {"query": query})


def _desktop_click(x: int, y: int, button: str = "left") -> str:
    """Hace clic en coordenadas absolutas de pantalla (píxeles)."""
    return _cu_post("click", {"x": x, "y": y, "button": button})


def _desktop_double_click(x: int, y: int) -> str:
    """Doble clic en coordenadas absolutas de pantalla."""
    step = _pilot_step({"type": "double_click", "x": x, "y": y})
    return json.dumps(step)


def _desktop_type(text: str) -> str:
    """
    Escribe texto con el teclado en el elemento que tiene el foco.
    Primero usa desktop_click o desktop_find para dar foco al campo.
    """
    return _cu_post("type", {"text": text})


def _desktop_hotkey(keys: str) -> str:
    """
    Ejecuta una combinación de teclas en el sistema.
    Ejemplos: 'win+r' (ejecutar), 'ctrl+c' (copiar), 'alt+f4' (cerrar),
    'ctrl+shift+t' (nueva pestaña), 'win+d' (escritorio), 'enter', 'escape'.
    """
    return _cu_post("key", {"key": keys})


def _desktop_scroll(x: int = 0, y: int = 0, direction: str = "down", amount: int = 3) -> str:
    """
    Scroll del ratón en la posición (x, y). direction: 'up' o 'down'.
    Si x=0 y y=0, hace scroll en la posición actual del cursor.
    """
    return _cu_post("scroll", {"x": x, "y": y, "direction": direction, "amount": amount})


def _desktop_navigate(url: str) -> str:
    """
    Abre una URL en el navegador predeterminado del sistema (no necesariamente Chrome).
    Ideal para abrir Google, Gmail, portales web, documentación, etc.
    """
    return _cu_post("navigate", {"url": url})


# ── Registro en tool_registry ─────────────────────────────────────────────────

tool_registry.register(ToolDefinition(
    name="desktop_screenshot",
    description=(
        "Captura el estado actual del escritorio. Devuelve las dimensiones de la pantalla, "
        "la ruta de la imagen guardada y una lista de controles UI visibles en la ventana "
        "activa. Úsala al inicio de una tarea para orientarte, o para verificar el resultado "
        "de una acción previa. Es el equivalente a 'abrir los ojos'."
    ),
    parameters={"type": "object", "properties": {}},
    fn=_desktop_screenshot,
    category="pilot",
))

tool_registry.register(ToolDefinition(
    name="desktop_read_screen",
    description=(
        "Lee la estructura de controles accesibles (botones, campos de texto, menús, etc.) "
        "de la ventana activa. Devuelve tipos de control, nombres y posiciones. "
        "Más preciso que un screenshot para saber exactamente qué elementos hay en pantalla "
        "y dónde están para hacer clic."
    ),
    parameters={
        "type": "object",
        "properties": {
            "window_title": {
                "type": "string",
                "description": "Título parcial de la ventana a leer. Vacío = ventana activa.",
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
        "Busca un elemento en la pantalla por descripción en lenguaje natural. "
        "Devuelve el nombre del control encontrado y sus coordenadas de centro. "
        "Usa el resultado de center_x, center_y para hacer desktop_click. "
        "Ejemplo: 'botón Aceptar', 'campo de búsqueda', 'botón de cerrar sesión'."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Descripción natural del elemento a encontrar.",
            },
        },
        "required": ["query"],
    },
    fn=_desktop_find,
    category="pilot",
))

tool_registry.register(ToolDefinition(
    name="desktop_click",
    description=(
        "Hace clic en coordenadas absolutas de pantalla (píxeles). "
        "Usa desktop_find primero para obtener las coordenadas del elemento objetivo. "
        "button puede ser 'left' (por defecto) o 'right'."
    ),
    parameters={
        "type": "object",
        "properties": {
            "x": {"type": "integer", "description": "Coordenada X en píxeles desde el borde izquierdo."},
            "y": {"type": "integer", "description": "Coordenada Y en píxeles desde el borde superior."},
            "button": {"type": "string", "enum": ["left", "right"], "default": "left"},
        },
        "required": ["x", "y"],
    },
    fn=_desktop_click,
    category="pilot",
))

tool_registry.register(ToolDefinition(
    name="desktop_type",
    description=(
        "Escribe texto con el teclado en el campo que tiene el foco. "
        "Antes de escribir, da foco al campo con desktop_click o desktop_find + desktop_click. "
        "Para confirmar un formulario, llama después a desktop_hotkey('enter')."
    ),
    parameters={
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Texto a escribir."},
        },
        "required": ["text"],
    },
    fn=_desktop_type,
    category="pilot",
))

tool_registry.register(ToolDefinition(
    name="desktop_hotkey",
    description=(
        "Ejecuta una combinación de teclas en el sistema operativo. "
        "Ejemplos útiles: 'enter' (confirmar), 'escape' (cancelar), "
        "'ctrl+c' (copiar), 'ctrl+v' (pegar), 'ctrl+a' (seleccionar todo), "
        "'ctrl+z' (deshacer), 'win+r' (abrir Ejecutar), 'alt+f4' (cerrar ventana), "
        "'win+d' (mostrar escritorio), 'ctrl+shift+esc' (Administrador de tareas)."
    ),
    parameters={
        "type": "object",
        "properties": {
            "keys": {
                "type": "string",
                "description": "Tecla o combinación. Usa + para combinar: 'ctrl+c', 'win+r'.",
            },
        },
        "required": ["keys"],
    },
    fn=_desktop_hotkey,
    category="pilot",
))

tool_registry.register(ToolDefinition(
    name="desktop_scroll",
    description=(
        "Hace scroll del ratón en la posición indicada. "
        "direction: 'down' (bajar) o 'up' (subir). "
        "amount: número de ticks (1-10, por defecto 3). "
        "Útil para desplazarte por listas, páginas largas, documentos."
    ),
    parameters={
        "type": "object",
        "properties": {
            "direction": {"type": "string", "enum": ["up", "down"], "default": "down"},
            "amount":    {"type": "integer", "description": "Ticks de scroll (1-10).", "default": 3},
            "x": {"type": "integer", "description": "Coordenada X. 0 = posición actual.", "default": 0},
            "y": {"type": "integer", "description": "Coordenada Y. 0 = posición actual.", "default": 0},
        },
    },
    fn=_desktop_scroll,
    category="pilot",
))

tool_registry.register(ToolDefinition(
    name="desktop_navigate",
    description=(
        "Abre una URL en el navegador predeterminado del sistema. "
        "Úsala para abrir páginas web (Google, Gmail, portales, documentación). "
        "Después usa desktop_screenshot o desktop_read_screen para ver el resultado."
    ),
    parameters={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL completa (https://...)."},
        },
        "required": ["url"],
    },
    fn=_desktop_navigate,
    category="pilot",
))
