"""
Computer Use tools — Loombit controla Chrome con ratón y teclado.

Estas tools permiten al agente navegar la web de forma autónoma:
  browser_navigate   — ir a una URL
  browser_click      — hacer clic en coordenadas o en un elemento (CSS selector)
  browser_type       — escribir texto en el elemento con foco
  browser_screenshot — capturar la pantalla (devuelve descripción + ruta)
  browser_read_page  — leer el texto visible de la página actual
  browser_key        — pulsar una tecla o combinación (Enter, Tab, Escape, etc.)
  browser_scroll     — hacer scroll en la página
  browser_find       — buscar un elemento por texto o descripción

El backend usa el servidor HTTP interno que el propio Loombit expone para
comunicarse con la extensión Claude-in-Chrome. Si la extensión no está conectada
las tools devuelven un error descriptivo en lugar de lanzar excepción.

Estado: 🟡 — arquitectura lista. Requiere que el operador corra con acceso a
         la extensión Claude-in-Chrome (tab group activo en el navegador).

CÓMO FUNCIONA INTERNAMENTE
───────────────────────────
El AgentLoop llama a estas tools igual que a las demás.
Aquí no usamos subprocess ni Playwright — usamos la API REST que el operador
expone a sí mismo en /computer-use/* (ver routers/computer.py).
Eso nos permite:
  1. Correr en Windows sin drivers adicionales
  2. Reusar la extensión Claude-in-Chrome ya instalada
  3. Tener un log centralizado de todas las acciones
"""

from __future__ import annotations

import json
import os

import httpx

from .registry import ToolDefinition, tool_registry

# URL base del propio operador (ajustable vía env)
_OPERATOR_BASE = os.environ.get("LOOMBIT_OPERATOR_URL", "http://127.0.0.1:8787")
_CU_BASE = f"{_OPERATOR_BASE}/computer-use"
_TIMEOUT = 20


def _cu_post(endpoint: str, payload: dict) -> str:
    """Llama al endpoint de computer-use del operador y devuelve texto."""
    try:
        r = httpx.post(f"{_CU_BASE}/{endpoint.lstrip('/')}", json=payload, timeout=_TIMEOUT)
        if r.status_code == 503:
            return "ERROR: extensión Chrome no conectada. Abre Chrome y asegúrate de que la extensión Loombit está activa."
        r.raise_for_status()
        data = r.json()
        return data.get("result", json.dumps(data))
    except httpx.ConnectError:
        return (
            "ERROR: no se pudo conectar con el operador Loombit. ¿Está corriendo en el puerto 8787?"
        )
    except httpx.HTTPStatusError as e:
        return f"ERROR HTTP {e.response.status_code}: {e.response.text[:300]}"
    except Exception as e:
        return f"ERROR inesperado en computer-use: {e}"


# ── Implementaciones ──────────────────────────────────────────────────────────


def _browser_navigate(url: str) -> str:
    return _cu_post("navigate", {"url": url})


def _browser_click(selector: str = "", x: int = 0, y: int = 0) -> str:
    return _cu_post("click", {"selector": selector, "x": x, "y": y})


def _browser_type(text: str) -> str:
    return _cu_post("type", {"text": text})


def _browser_key(key: str) -> str:
    """Pulsa una tecla o combinación: 'Enter', 'Tab', 'ctrl+a', 'Escape', etc."""
    return _cu_post("key", {"key": key})


def _browser_scroll(direction: str = "down", amount: int = 3) -> str:
    return _cu_post("scroll", {"direction": direction, "amount": amount})


def _browser_screenshot() -> str:
    return _cu_post("screenshot", {})


def _browser_read_page() -> str:
    return _cu_post("read_page", {})


def _browser_find(query: str) -> str:
    """Busca un elemento en la página por descripción o texto visible."""
    return _cu_post("find", {"query": query})


# ── Registro en tool_registry ─────────────────────────────────────────────────

tool_registry.register(
    ToolDefinition(
        name="browser_navigate",
        description=(
            "Navega a una URL en el navegador Chrome. "
            "Úsala para abrir páginas web, Google, Gmail, portales, etc. "
            "Espera a que la página cargue antes de interactuar con ella."
        ),
        parameters={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL completa a la que navegar (https://...).",
                },
            },
            "required": ["url"],
        },
        fn=_browser_navigate,
        category="computer",
    )
)

tool_registry.register(
    ToolDefinition(
        name="browser_click",
        description=(
            "Hace clic en un elemento de la página. "
            "Puedes indicar el elemento con un selector CSS (ej. 'button[type=submit]', '#login-btn') "
            "o con coordenadas de pantalla (x, y). "
            "Usa browser_find primero si no sabes el selector exacto."
        ),
        parameters={
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "Selector CSS del elemento. Dejar vacío si usas coordenadas.",
                    "default": "",
                },
                "x": {
                    "type": "integer",
                    "description": "Coordenada X en píxeles. Solo si no hay selector.",
                    "default": 0,
                },
                "y": {
                    "type": "integer",
                    "description": "Coordenada Y en píxeles. Solo si no hay selector.",
                    "default": 0,
                },
            },
        },
        fn=_browser_click,
        category="computer",
    )
)

tool_registry.register(
    ToolDefinition(
        name="browser_type",
        description=(
            "Escribe texto en el campo de entrada que tiene el foco. "
            "Primero haz clic en el campo con browser_click, luego llama a browser_type. "
            "Úsala para rellenar formularios, buscadores, asuntos de correo, etc."
        ),
        parameters={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Texto a escribir."},
            },
            "required": ["text"],
        },
        fn=_browser_type,
        category="computer",
    )
)

tool_registry.register(
    ToolDefinition(
        name="browser_key",
        description=(
            "Pulsa una tecla o combinación de teclado en el navegador. "
            "Ejemplos: 'Enter' (confirmar), 'Tab' (siguiente campo), 'Escape' (cerrar), "
            "'ctrl+a' (seleccionar todo), 'ctrl+c' (copiar), 'Backspace' (borrar). "
            "Úsala después de browser_type para enviar un formulario."
        ),
        parameters={
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Tecla o combinación (Enter, Tab, ctrl+a, etc.).",
                },
            },
            "required": ["key"],
        },
        fn=_browser_key,
        category="computer",
    )
)

tool_registry.register(
    ToolDefinition(
        name="browser_scroll",
        description=(
            "Hace scroll en la página del navegador. "
            "direction puede ser 'up' o 'down'. "
            "amount es el número de ticks de scroll (1-10)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "direction": {"type": "string", "enum": ["up", "down"], "default": "down"},
                "amount": {
                    "type": "integer",
                    "description": "Ticks de scroll (1-10).",
                    "default": 3,
                },
            },
        },
        fn=_browser_scroll,
        category="computer",
    )
)

tool_registry.register(
    ToolDefinition(
        name="browser_screenshot",
        description=(
            "Captura una imagen de la pantalla actual del navegador y devuelve "
            "una descripción del contenido visible. "
            "Úsala para entender qué hay en pantalla antes de hacer clic."
        ),
        parameters={"type": "object", "properties": {}},
        fn=_browser_screenshot,
        category="computer",
    )
)

tool_registry.register(
    ToolDefinition(
        name="browser_read_page",
        description=(
            "Lee y devuelve el texto visible de la página actual del navegador. "
            "Útil para extraer contenido sin necesidad de captura de pantalla. "
            "Devuelve el texto limpio (sin HTML). Máx. 6000 caracteres."
        ),
        parameters={"type": "object", "properties": {}},
        fn=_browser_read_page,
        category="computer",
    )
)

tool_registry.register(
    ToolDefinition(
        name="browser_find",
        description=(
            "Busca un elemento en la página actual por descripción o texto visible. "
            "Devuelve el selector CSS del elemento encontrado o un mensaje de error. "
            "Úsala antes de browser_click cuando no conoces el selector exacto. "
            "Ejemplos de query: 'botón de búsqueda', 'campo de email', 'enlace Iniciar sesión'."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Descripción en lenguaje natural del elemento a encontrar.",
                },
            },
            "required": ["query"],
        },
        fn=_browser_find,
        category="computer",
    )
)
