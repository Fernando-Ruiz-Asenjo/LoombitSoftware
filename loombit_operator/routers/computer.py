"""
Router de Computer Use — puente entre AgentLoop y el escritorio local.

Implementación real mediante Skill W Loombit Pilot:
  - screenshot   → PIL.ImageGrab (real, siempre disponible)
  - click        → pynput mouse (real, siempre disponible)
  - type / key   → pynput keyboard (real, siempre disponible)
  - scroll       → pynput mouse scroll (real)
  - navigate     → webbrowser.open (real)
  - read_page    → inspect_controls via pywinauto (real si instalado)
  - find         → inspect_controls filtrado por query (real si instalado)

Estado: 🟠 Parcial
  - screenshot, click, type, key, scroll, navigate → 🟢 reales
  - read_page, find → 🟠 reales solo con pywinauto instalado

Endpoints:
  GET  /computer-use/status
  POST /computer-use/navigate
  POST /computer-use/click
  POST /computer-use/type
  POST /computer-use/key
  POST /computer-use/scroll
  POST /computer-use/screenshot
  POST /computer-use/read_page
  POST /computer-use/find
"""
from __future__ import annotations

import base64
import io
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/computer-use", tags=["computer-use"])


# ── Modelos ───────────────────────────────────────────────────────────────────

class NavigateRequest(BaseModel):
    url: str

class ClickRequest(BaseModel):
    selector: str = ""
    x: int = 0
    y: int = 0
    button: str = "left"

class TypeRequest(BaseModel):
    text: str

class KeyRequest(BaseModel):
    key: str

class ScrollRequest(BaseModel):
    x: int = 0
    y: int = 0
    direction: str = "down"
    amount: int = 3

class FindRequest(BaseModel):
    query: str


# ── Status ────────────────────────────────────────────────────────────────────

@router.get("/status")
async def computer_status() -> dict:
    """Estado de los backends de computer use."""
    try:
        import pynput  # noqa: F401
        pynput_ok = True
    except ImportError:
        pynput_ok = False

    pywinauto_error = ""
    try:
        import pywinauto  # noqa: F401
        pywinauto_ok = True
    except Exception as _e:
        pywinauto_ok = False
        pywinauto_error = f"{type(_e).__name__}: {_e}"

    return {
        "pynput": "ok" if pynput_ok else "missing — pip install pynput",
        "pywinauto": "ok" if pywinauto_ok else f"error: {pywinauto_error}",
        "pillow": "ok",  # requerida en requirements.txt
        "capabilities": {
            "screenshot": True,
            "click": pynput_ok,
            "type": pynput_ok,
            "key": pynput_ok,
            "scroll": pynput_ok,
            "navigate": True,
            "read_page": pywinauto_ok,
            "find": pywinauto_ok,
        },
    }


# ── Navigate ──────────────────────────────────────────────────────────────────

@router.post("/navigate")
async def navigate(body: NavigateRequest) -> dict:
    from loombit_operator.pilot.windows_control import open_url
    result = open_url(body.url)
    return {"result": result}


# ── Screenshot ────────────────────────────────────────────────────────────────

@router.post("/screenshot")
async def screenshot() -> dict:
    from loombit_operator.pilot.screen import take_screenshot
    try:
        from loombit_operator.config import get_settings
        settings = get_settings()
        save_dir = Path(settings.agent_run_store_path).parent / "skill_pilot"
    except Exception:
        save_dir = Path("runtime/local/skill_pilot")

    result = take_screenshot(save_dir=save_dir, include_base64=True)
    if "error" in result:
        return {"result": f"ERROR: {result['error']}"}

    # El agente recibe dimensiones + ruta. El base64 se devuelve también.
    return {
        "result": (
            f"Screenshot capturado: {result['width']}x{result['height']} px. "
            f"Guardado en: {result.get('saved_path', 'no guardado')}."
        ),
        "width": result["width"],
        "height": result["height"],
        "saved_path": result.get("saved_path"),
        "base64": result.get("base64"),
    }


# ── Click ─────────────────────────────────────────────────────────────────────

@router.post("/click")
async def click(body: ClickRequest) -> dict:
    from loombit_operator.pilot.input_control import mouse_click
    if body.selector:
        # Sin pywinauto no podemos resolver selectores CSS fuera del navegador
        logger.warning("click: selector '%s' ignorado — usa coordenadas x,y", body.selector)
    result = mouse_click(body.x, body.y, button=body.button)
    return {"result": result}


# ── Type ──────────────────────────────────────────────────────────────────────

@router.post("/type")
async def type_text(body: TypeRequest) -> dict:
    from loombit_operator.pilot.input_control import keyboard_type
    result = keyboard_type(body.text)
    return {"result": result}


# ── Key ───────────────────────────────────────────────────────────────────────

@router.post("/key")
async def press_key(body: KeyRequest) -> dict:
    from loombit_operator.pilot.input_control import keyboard_hotkey, keyboard_press
    if "+" in body.key:
        result = keyboard_hotkey(body.key)
    else:
        result = keyboard_press(body.key)
    return {"result": result}


# ── Scroll ────────────────────────────────────────────────────────────────────

@router.post("/scroll")
async def scroll(body: ScrollRequest) -> dict:
    from loombit_operator.pilot.input_control import mouse_scroll
    result = mouse_scroll(body.x, body.y, direction=body.direction, amount=body.amount)
    return {"result": result}


# ── Read page ─────────────────────────────────────────────────────────────────

@router.post("/read_page")
async def read_page() -> dict:
    from loombit_operator.pilot.windows_control import inspect_controls
    result = inspect_controls(limit=60)
    if result.get("error"):
        return {"result": f"ERROR: {result['error']}"}
    controls = result.get("controls", [])
    lines = [f"[{c['control_type']}] {c['name']!r}" for c in controls if c.get("name")]
    text = "\n".join(lines[:50])
    return {
        "result": text or "(sin controles con nombre visibles)",
        "controls_count": len(controls),
        "window_title": result.get("window_title", ""),
    }


# ── Find ──────────────────────────────────────────────────────────────────────

@router.post("/find")
async def find(body: FindRequest) -> dict:
    from loombit_operator.pilot.windows_control import inspect_controls
    result = inspect_controls(limit=100)
    if result.get("error"):
        return {"result": f"ERROR: {result['error']}"}

    query_lo = body.query.lower()
    matches = [
        c for c in result.get("controls", [])
        if query_lo in (c.get("name") or "").lower()
        or query_lo in (c.get("automation_id") or "").lower()
    ]

    if not matches:
        return {"result": f"No se encontró ningún control que coincida con: '{body.query}'"}

    best = matches[0]
    rect = best.get("rect", {})
    center_x = (rect.get("left", 0) + rect.get("right", 0)) // 2
    center_y = (rect.get("top", 0) + rect.get("bottom", 0)) // 2
    return {
        "result": (
            f"Encontrado: [{best['control_type']}] '{best['name']}' "
            f"en ({center_x}, {center_y}). "
            f"Usa click con x={center_x}, y={center_y}."
        ),
        "control": best,
        "center_x": center_x,
        "center_y": center_y,
    }
