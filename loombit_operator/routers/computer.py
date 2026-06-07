"""
Router de Computer Use — puente entre AgentLoop y el escritorio local.

Estado: 🟠 Parcial
  - screenshot, click, type, key, scroll, navigate → 🟢 reales
  - read_page, find → 🟠 reales solo con pywinauto instalado

Endpoints:
  GET  /computer-use/status
  GET  /computer-use/cursor_position
  GET  /computer-use/clipboard
  POST /computer-use/navigate
  POST /computer-use/click
  POST /computer-use/double_click
  POST /computer-use/triple_click
  POST /computer-use/mouse_move
  POST /computer-use/drag
  POST /computer-use/mouse_down
  POST /computer-use/mouse_up
  POST /computer-use/type
  POST /computer-use/key
  POST /computer-use/hold_key_press
  POST /computer-use/hold_key_release
  POST /computer-use/scroll
  POST /computer-use/screenshot
  POST /computer-use/zoom
  POST /computer-use/read_page
  POST /computer-use/find
  POST /computer-use/clipboard
  POST /computer-use/open_application
  POST /computer-use/wait
  POST /computer-use/batch
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/computer-use", tags=["computer-use"])


# Models


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


class DragRequest(BaseModel):
    x1: int
    y1: int
    x2: int
    y2: int
    button: str = "left"
    duration: float = 0.3


class MouseDownRequest(BaseModel):
    x: int
    y: int
    button: str = "left"


class MouseUpRequest(BaseModel):
    x: int
    y: int
    button: str = "left"


class MoveRequest(BaseModel):
    x: int
    y: int


class HoldKeyRequest(BaseModel):
    key: str


class WaitRequest(BaseModel):
    seconds: float = 1.0


class ZoomRequest(BaseModel):
    x0: int
    y0: int
    x1: int
    y1: int


class ClipboardWriteRequest(BaseModel):
    text: str


class OpenAppRequest(BaseModel):
    app_name: str


class BatchAction(BaseModel):
    action: str
    params: dict = {}


class BatchRequest(BaseModel):
    actions: list[BatchAction]


# Status


@router.get("/status")
async def computer_status() -> dict:
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
        "pynput": "ok" if pynput_ok else "missing",
        "pywinauto": "ok" if pywinauto_ok else f"error: {pywinauto_error}",
        "pillow": "ok",
        "capabilities": {
            "screenshot": True,
            "click": pynput_ok,
            "double_click": pynput_ok,
            "triple_click": pynput_ok,
            "mouse_move": pynput_ok,
            "drag": pynput_ok,
            "mouse_down": pynput_ok,
            "mouse_up": pynput_ok,
            "type": pynput_ok,
            "key": pynput_ok,
            "hold_key": pynput_ok,
            "scroll": pynput_ok,
            "navigate": True,
            "zoom": True,
            "cursor_position": pynput_ok,
            "clipboard": True,
            "open_application": True,
            "wait": True,
            "batch": True,
            "read_page": pywinauto_ok,
            "find": pywinauto_ok,
        },
    }


# Navigate


@router.post("/navigate")
async def navigate(body: NavigateRequest) -> dict:
    from loombit_operator.pilot.windows_control import open_url

    result = open_url(body.url)
    return {"result": result}


# Screenshot


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


# Click


@router.post("/click")
async def click(body: ClickRequest) -> dict:
    from loombit_operator.pilot.input_control import mouse_click

    if body.selector:
        logger.warning("click: selector ignorado — usa coordenadas x,y")
    result = mouse_click(body.x, body.y, button=body.button)
    return {"result": result}


# Double / Triple click


@router.post("/double_click")
async def double_click(body: ClickRequest) -> dict:
    from loombit_operator.pilot.input_control import mouse_click

    result = mouse_click(body.x, body.y, button=body.button, count=2)
    return {"result": result}


@router.post("/triple_click")
async def triple_click(body: ClickRequest) -> dict:
    from loombit_operator.pilot.input_control import mouse_click

    result = mouse_click(body.x, body.y, button=body.button, count=3)
    return {"result": result}


# Mouse move


@router.post("/mouse_move")
async def mouse_move_endpoint(body: MoveRequest) -> dict:
    from loombit_operator.pilot.input_control import mouse_move as _move

    result = _move(body.x, body.y)
    return {"result": result}


# Drag


@router.post("/drag")
async def drag(body: DragRequest) -> dict:
    from loombit_operator.pilot.input_control import mouse_drag

    result = mouse_drag(
        body.x1, body.y1, body.x2, body.y2, button=body.button, duration=body.duration
    )
    return {"result": result}


# Mouse down / up


@router.post("/mouse_down")
async def mouse_down(body: MouseDownRequest) -> dict:
    from loombit_operator.pilot.input_control import mouse_button_down

    return {"result": mouse_button_down(body.x, body.y, button=body.button)}


@router.post("/mouse_up")
async def mouse_up(body: MouseUpRequest) -> dict:
    from loombit_operator.pilot.input_control import mouse_button_up

    return {"result": mouse_button_up(body.x, body.y, button=body.button)}


# Type


@router.post("/type")
async def type_text(body: TypeRequest) -> dict:
    from loombit_operator.pilot.input_control import keyboard_type

    result = keyboard_type(body.text)
    return {"result": result}


# Key


@router.post("/key")
async def press_key(body: KeyRequest) -> dict:
    from loombit_operator.pilot.input_control import keyboard_hotkey, keyboard_press

    if "+" in body.key:
        result = keyboard_hotkey(body.key)
    else:
        result = keyboard_press(body.key)
    return {"result": result}


# Hold key


@router.post("/hold_key_press")
async def hold_key_press(body: HoldKeyRequest) -> dict:
    from loombit_operator.pilot.input_control import keyboard_hold_press

    return {"result": keyboard_hold_press(body.key)}


@router.post("/hold_key_release")
async def hold_key_release(body: HoldKeyRequest) -> dict:
    from loombit_operator.pilot.input_control import keyboard_hold_release

    return {"result": keyboard_hold_release(body.key)}


# Scroll


@router.post("/scroll")
async def scroll(body: ScrollRequest) -> dict:
    from loombit_operator.pilot.input_control import mouse_scroll

    result = mouse_scroll(body.x, body.y, direction=body.direction, amount=body.amount)
    return {"result": result}


# Read page


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


# Find


@router.post("/find")
async def find(body: FindRequest) -> dict:
    from loombit_operator.pilot.windows_control import inspect_controls

    result = inspect_controls(limit=100)
    if result.get("error"):
        return {"result": f"ERROR: {result['error']}"}

    query_lo = body.query.lower()
    matches = [
        c
        for c in result.get("controls", [])
        if query_lo in (c.get("name") or "").lower()
        or query_lo in (c.get("automation_id") or "").lower()
    ]

    if not matches:
        return {"result": f"No se encontro ningun control: '{body.query}'"}

    best = matches[0]
    rect = best.get("rect", {})
    center_x = (rect.get("left", 0) + rect.get("right", 0)) // 2
    center_y = (rect.get("top", 0) + rect.get("bottom", 0)) // 2
    return {
        "result": (
            f"Encontrado: [{best['control_type']}] '{best['name']}' "
            f"en ({center_x}, {center_y})."
        ),
        "control": best,
        "center_x": center_x,
        "center_y": center_y,
    }


# Zoom (screenshot de region)


@router.post("/zoom")
async def zoom(body: ZoomRequest) -> dict:
    from loombit_operator.pilot.screen import take_screenshot

    region = (body.x0, body.y0, body.x1, body.y1)
    result = take_screenshot(include_base64=True, region=region)
    if "error" in result:
        return {"result": f"ERROR: {result['error']}"}
    return {
        "result": f"Region capturada: {result['width']}x{result['height']} px.",
        "width": result["width"],
        "height": result["height"],
        "base64": result.get("base64"),
    }


# Cursor position


@router.get("/cursor_position")
async def get_cursor_position() -> dict:
    from loombit_operator.pilot.input_control import cursor_position

    result = cursor_position()
    return {"result": result}


# Clipboard


@router.get("/clipboard")
async def clipboard_get() -> dict:
    from loombit_operator.pilot.input_control import clipboard_read

    return {"result": clipboard_read()}


@router.post("/clipboard")
async def clipboard_set(body: ClipboardWriteRequest) -> dict:
    from loombit_operator.pilot.input_control import clipboard_write

    return {"result": clipboard_write(body.text)}


# Open application


@router.post("/open_application")
async def open_app(body: OpenAppRequest) -> dict:
    from loombit_operator.pilot.input_control import open_application

    return {"result": open_application(body.app_name)}


# Wait


@router.post("/wait")
async def wait_action(body: WaitRequest) -> dict:
    import asyncio

    secs = max(0.1, min(body.seconds, 10.0))
    await asyncio.sleep(secs)
    return {"result": f"Esperado {secs}s"}


# Batch


@router.post("/batch")
async def batch(body: BatchRequest) -> dict:
    """
    Ejecuta una secuencia de acciones sin round-trips.
    Equivalente a computer_batch de Claude Computer Use.
    """
    import httpx

    results = []
    base = "http://127.0.0.1:8787/computer-use"
    get_endpoints = {"status", "cursor_position", "clipboard"}

    async with httpx.AsyncClient(timeout=30) as client:
        for step in body.actions:
            action = step.action
            params = step.params
            try:
                if action in get_endpoints:
                    r = await client.get(f"{base}/{action}")
                else:
                    r = await client.post(f"{base}/{action}", json=params)
                r.raise_for_status()
                results.append({"action": action, "ok": True, "result": r.json()})
            except Exception as exc:
                results.append({"action": action, "ok": False, "error": str(exc)})
                break

    return {"results": results, "completed": len(results)}
