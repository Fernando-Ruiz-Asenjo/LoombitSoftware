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


def _desktop_wait_for_window(title: str, timeout: float = 10.0) -> str:
    return _cu_post("wait_for_window", {"title": title, "timeout": timeout})


def _desktop_click_accessibility(
    name: str = "", automation_id: str = "", window_title: str = ""
) -> str:
    return _cu_post(
        "click_accessibility",
        {
            "name": name,
            "automation_id": automation_id,
            "window_title": window_title,
        },
    )


def _desktop_screen_changed(threshold: float = 0.02) -> str:
    return _cu_post("screen_changed", {"threshold": threshold})


def _desktop_ui_snapshot(
    process_name: str = "", title: str = "", interactive_only: bool = True
) -> str:
    return _cu_post(
        "ui_snapshot",
        {
            "process_name": process_name,
            "title": title,
            "interactive_only": interactive_only,
        },
    )


def _desktop_type(text: str) -> str:
    return _cu_post("type", {"text": text})


def _desktop_hotkey(keys: str) -> str:
    return _cu_post("key", {"key": keys})


def _desktop_scroll(x: int = 0, y: int = 0, direction: str = "down", amount: int = 3) -> str:
    return _cu_post("scroll", {"x": x, "y": y, "direction": direction, "amount": amount})


def _desktop_navigate(url: str) -> str:
    return _cu_post("navigate", {"url": url})


# Registry

tool_registry.register(
    ToolDefinition(
        name="desktop_screenshot",
        description="Captura el escritorio y lista controles visibles. Usar al inicio y para verificar.",
        parameters={"type": "object", "properties": {}},
        fn=_desktop_screenshot,
        category="pilot",
    )
)

tool_registry.register(
    ToolDefinition(
        name="desktop_read_screen",
        description="Lee controles accesibles (botones, campos) de la ventana activa. Mas preciso que screenshot.",
        parameters={
            "type": "object",
            "properties": {
                "window_title": {
                    "type": "string",
                    "description": "Titulo parcial. Vacio=activa.",
                    "default": "",
                },
            },
        },
        fn=_desktop_read_screen,
        category="pilot",
    )
)

tool_registry.register(
    ToolDefinition(
        name="desktop_find",
        description="Busca elemento por descripcion en lenguaje natural. Devuelve coordenadas para desktop_click.",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
        fn=_desktop_find,
        category="pilot",
    )
)

tool_registry.register(
    ToolDefinition(
        name="desktop_click",
        description="Clic en coordenadas absolutas (pixeles). button: left|right.",
        parameters={
            "type": "object",
            "properties": {
                "x": {"type": "integer"},
                "y": {"type": "integer"},
                "button": {"type": "string", "enum": ["left", "right"], "default": "left"},
            },
            "required": ["x", "y"],
        },
        fn=_desktop_click,
        category="pilot",
    )
)

tool_registry.register(
    ToolDefinition(
        name="desktop_double_click",
        description="Doble clic en coordenadas absolutas. Para abrir ficheros o seleccionar palabra.",
        parameters={
            "type": "object",
            "properties": {
                "x": {"type": "integer"},
                "y": {"type": "integer"},
            },
            "required": ["x", "y"],
        },
        fn=_desktop_double_click,
        category="pilot",
    )
)

tool_registry.register(
    ToolDefinition(
        name="desktop_triple_click",
        description="Triple clic para seleccionar toda la linea o campo de texto.",
        parameters={
            "type": "object",
            "properties": {
                "x": {"type": "integer"},
                "y": {"type": "integer"},
            },
            "required": ["x", "y"],
        },
        fn=_desktop_triple_click,
        category="pilot",
    )
)

tool_registry.register(
    ToolDefinition(
        name="desktop_mouse_move",
        description="Mueve el cursor a (x,y) sin clic. Para hover states o tooltips.",
        parameters={
            "type": "object",
            "properties": {
                "x": {"type": "integer"},
                "y": {"type": "integer"},
            },
            "required": ["x", "y"],
        },
        fn=_desktop_mouse_move,
        category="pilot",
    )
)

tool_registry.register(
    ToolDefinition(
        name="desktop_drag",
        description="Arrastra desde (x1,y1) hasta (x2,y2). Para sliders, ventanas, seleccion de texto.",
        parameters={
            "type": "object",
            "properties": {
                "x1": {"type": "integer"},
                "y1": {"type": "integer"},
                "x2": {"type": "integer"},
                "y2": {"type": "integer"},
            },
            "required": ["x1", "y1", "x2", "y2"],
        },
        fn=_desktop_drag,
        category="pilot",
    )
)

tool_registry.register(
    ToolDefinition(
        name="desktop_mouse_down",
        description="Pulsa el boton izquierdo en (x,y) sin soltarlo. Combinar con mouse_move + mouse_up.",
        parameters={
            "type": "object",
            "properties": {
                "x": {"type": "integer"},
                "y": {"type": "integer"},
            },
            "required": ["x", "y"],
        },
        fn=_desktop_mouse_down,
        category="pilot",
    )
)

tool_registry.register(
    ToolDefinition(
        name="desktop_mouse_up",
        description="Suelta el boton izquierdo en (x,y). Usar tras desktop_mouse_down.",
        parameters={
            "type": "object",
            "properties": {
                "x": {"type": "integer"},
                "y": {"type": "integer"},
            },
            "required": ["x", "y"],
        },
        fn=_desktop_mouse_up,
        category="pilot",
    )
)

tool_registry.register(
    ToolDefinition(
        name="desktop_type",
        description="Escribe texto en el campo con foco. Da foco con desktop_click primero.",
        parameters={
            "type": "object",
            "properties": {
                "text": {"type": "string"},
            },
            "required": ["text"],
        },
        fn=_desktop_type,
        category="pilot",
    )
)

tool_registry.register(
    ToolDefinition(
        name="desktop_hotkey",
        description="Tecla o combinacion: 'enter','ctrl+c','win+r','alt+f4'. Usa + para combinar.",
        parameters={
            "type": "object",
            "properties": {
                "keys": {"type": "string"},
            },
            "required": ["keys"],
        },
        fn=_desktop_hotkey,
        category="pilot",
    )
)

tool_registry.register(
    ToolDefinition(
        name="desktop_scroll",
        description="Scroll en (x,y). direction: up|down. amount: 1-10.",
        parameters={
            "type": "object",
            "properties": {
                "direction": {"type": "string", "enum": ["up", "down"], "default": "down"},
                "amount": {"type": "integer", "default": 3},
                "x": {"type": "integer", "default": 0},
                "y": {"type": "integer", "default": 0},
            },
        },
        fn=_desktop_scroll,
        category="pilot",
    )
)

tool_registry.register(
    ToolDefinition(
        name="desktop_navigate",
        description="Abre URL en el navegador del sistema.",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string"},
            },
            "required": ["url"],
        },
        fn=_desktop_navigate,
        category="pilot",
    )
)

tool_registry.register(
    ToolDefinition(
        name="desktop_wait",
        description="Espera N segundos (max 10). Para cargas o animaciones.",
        parameters={
            "type": "object",
            "properties": {
                "seconds": {"type": "number", "default": 1.0},
            },
        },
        fn=_desktop_wait,
        category="pilot",
    )
)

tool_registry.register(
    ToolDefinition(
        name="desktop_zoom",
        description="Captura region (x0,y0)-(x1,y1) en detalle. Para leer texto pequeno.",
        parameters={
            "type": "object",
            "properties": {
                "x0": {"type": "integer"},
                "y0": {"type": "integer"},
                "x1": {"type": "integer"},
                "y1": {"type": "integer"},
            },
            "required": ["x0", "y0", "x1", "y1"],
        },
        fn=_desktop_zoom,
        category="pilot",
    )
)

tool_registry.register(
    ToolDefinition(
        name="desktop_cursor_position",
        description="Devuelve la posicion actual del cursor del raton en pixeles (x, y).",
        parameters={"type": "object", "properties": {}},
        fn=_desktop_cursor_position,
        category="pilot",
    )
)

tool_registry.register(
    ToolDefinition(
        name="desktop_clipboard_read",
        description="Lee texto del portapapeles.",
        parameters={"type": "object", "properties": {}},
        fn=_desktop_clipboard_read,
        category="pilot",
    )
)

tool_registry.register(
    ToolDefinition(
        name="desktop_clipboard_write",
        description="Escribe texto en el portapapeles. Pegar con desktop_hotkey('ctrl+v').",
        parameters={
            "type": "object",
            "properties": {
                "text": {"type": "string"},
            },
            "required": ["text"],
        },
        fn=_desktop_clipboard_write,
        category="pilot",
    )
)

tool_registry.register(
    ToolDefinition(
        name="desktop_open_app",
        description="Lanza app Windows: 'notepad','chrome','explorer','code', etc.",
        parameters={
            "type": "object",
            "properties": {
                "app_name": {"type": "string"},
            },
            "required": ["app_name"],
        },
        fn=_desktop_open_app,
        category="pilot",
    )
)

tool_registry.register(
    ToolDefinition(
        name="desktop_batch",
        description="Secuencia de acciones en un llamado. actions: [{action, params}]. Para en el primer error.",
        parameters={
            "type": "object",
            "properties": {
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
            },
            "required": ["actions"],
        },
        fn=_desktop_batch,
        category="pilot",
    )
)

tool_registry.register(
    ToolDefinition(
        name="desktop_wait_for_window",
        description="Espera (polling) hasta que aparezca ventana con titulo dado. timeout en segundos.",
        parameters={
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "timeout": {"type": "number", "default": 10.0},
            },
            "required": ["title"],
        },
        fn=_desktop_wait_for_window,
        category="pilot",
    )
)

tool_registry.register(
    ToolDefinition(
        name="desktop_click_accessibility",
        description="Clic por arbol de accesibilidad (mas estable que coordenadas). name o automation_id del control.",
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string", "default": ""},
                "automation_id": {"type": "string", "default": ""},
                "window_title": {"type": "string", "default": ""},
            },
        },
        fn=_desktop_click_accessibility,
        category="pilot",
    )
)

tool_registry.register(
    ToolDefinition(
        name="desktop_screen_changed",
        description="Compara pantalla actual con la anterior. Devuelve changed=True si diff > threshold. Usar para verificar que una accion tuvo efecto.",
        parameters={
            "type": "object",
            "properties": {
                "threshold": {"type": "number", "default": 0.02},
            },
        },
        fn=_desktop_screen_changed,
        category="pilot",
    )
)

tool_registry.register(
    ToolDefinition(
        name="desktop_ui_snapshot",
        description=(
            "VIA PREFERENTE: lee el arbol de accesibilidad (UIA) de la ventana y "
            "devuelve los controles accionables (name, automation_id, valor, centro). "
            "Usar ANTES que screenshot+coordenadas; luego actuar con "
            "desktop_click_accessibility por name/automation_id."
        ),
        parameters={
            "type": "object",
            "properties": {
                "process_name": {"type": "string", "default": ""},
                "title": {"type": "string", "default": ""},
                "interactive_only": {"type": "boolean", "default": True},
            },
        },
        fn=_desktop_ui_snapshot,
        category="pilot",
    )
)


def _save_screenshot_to_file(filename: str = "") -> str:
    """
    Captura la pantalla completa y la guarda como fichero PNG.
    Devuelve la ruta absoluta del fichero guardado.
    Usar cuando se necesita adjuntar una captura de pantalla a un correo u otro documento.
    """
    try:
        r = httpx.post(f"{_BASE}/computer-use/screenshot", json={}, timeout=_TIMEOUT)
        r.raise_for_status()
        data = r.json()

        saved_path = data.get("saved_path", "")
        if saved_path:
            # Si el usuario pidió un nombre específico, renombrar el fichero
            if filename:
                from pathlib import Path

                p = Path(saved_path)
                new_path = p.parent / filename
                if not new_path.suffix:
                    new_path = new_path.with_suffix(".png")
                p.rename(new_path)
                saved_path = str(new_path)

            return json.dumps(
                {
                    "ok": True,
                    "path": saved_path,
                    "width": data.get("width"),
                    "height": data.get("height"),
                    "message": f"Captura guardada en: {saved_path}",
                },
                ensure_ascii=False,
            )

        # Fallback: guardar base64 manualmente si el endpoint no devuelve saved_path
        b64 = data.get("base64", "")
        if b64:
            import base64
            from pathlib import Path
            from datetime import datetime

            save_dir = Path("runtime/local/skill_pilot")
            save_dir.mkdir(parents=True, exist_ok=True)
            fname = filename or f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            if not fname.endswith(".png"):
                fname += ".png"
            out = save_dir / fname
            out.write_bytes(base64.b64decode(b64))
            return json.dumps(
                {
                    "ok": True,
                    "path": str(out),
                    "message": f"Captura guardada en: {out}",
                },
                ensure_ascii=False,
            )

        return json.dumps(
            {"ok": False, "error": "El backend no devolvió ruta ni imagen"}, ensure_ascii=False
        )
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)


tool_registry.register(
    ToolDefinition(
        name="save_screenshot_to_file",
        description=(
            "Captura la pantalla completa y guarda el PNG en disco. "
            "Devuelve la ruta del fichero para poder adjuntarlo a un correo (gmail_send attachment_path). "
            "Usar siempre que el usuario pida adjuntar una captura de pantalla a un correo. "
            "NUNCA pedir al usuario que tome la captura manualmente."
        ),
        parameters={
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "default": "",
                    "description": "Nombre del fichero (opcional). Si no se indica, se genera con timestamp.",
                },
            },
        },
        fn=_save_screenshot_to_file,
        category="pilot",
    )
)
