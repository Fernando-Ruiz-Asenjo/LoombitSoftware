"""
input_control.py — ratón y teclado via pynput.

Proporciona primitivas de bajo nivel:
  mouse_move, mouse_click, mouse_double_click, mouse_scroll
  keyboard_type, keyboard_press, keyboard_hotkey

Todas las funciones son síncronas. El executor las llama desde asyncio
mediante run_in_executor si fuera necesario (actualmente el GIL no bloquea).

Requiere: pynput>=1.7.6
"""
from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

# ── Importación defensiva ─────────────────────────────────────────────────────

try:
    from pynput.mouse import Button, Controller as _MouseCtrl  # type: ignore
    from pynput.keyboard import Controller as _KbCtrl, Key, KeyCode  # type: ignore
    _PYNPUT_OK = True
except ImportError:
    _PYNPUT_OK = False
    logger.warning("pynput no instalado — input_control en modo stub")

# ── Mapa de teclas especiales ─────────────────────────────────────────────────

_KEY_MAP: dict[str, Any] = {}

def _build_key_map() -> None:
    if not _PYNPUT_OK:
        return
    global _KEY_MAP
    _KEY_MAP = {
        "ctrl": Key.ctrl, "control": Key.ctrl,
        "shift": Key.shift,
        "alt": Key.alt,
        "win": Key.cmd, "cmd": Key.cmd, "super": Key.cmd,
        "enter": Key.enter, "return": Key.enter,
        "tab": Key.tab,
        "escape": Key.esc, "esc": Key.esc,
        "backspace": Key.backspace,
        "delete": Key.delete, "del": Key.delete,
        "space": Key.space,
        "up": Key.up, "down": Key.down, "left": Key.left, "right": Key.right,
        "home": Key.home, "end": Key.end,
        "page_up": Key.page_up, "pageup": Key.page_up,
        "page_down": Key.page_down, "pagedown": Key.page_down,
        "insert": Key.insert,
        "f1": Key.f1, "f2": Key.f2, "f3": Key.f3, "f4": Key.f4,
        "f5": Key.f5, "f6": Key.f6, "f7": Key.f7, "f8": Key.f8,
        "f9": Key.f9, "f10": Key.f10, "f11": Key.f11, "f12": Key.f12,
        "print_screen": Key.print_screen,
        "caps_lock": Key.caps_lock,
        "num_lock": Key.num_lock,
    }

_build_key_map()


def _resolve_key(part: str) -> Any:
    """Convierte un string de tecla a un objeto pynput Key o KeyCode."""
    lo = part.lower().strip()
    if lo in _KEY_MAP:
        return _KEY_MAP[lo]
    # Tecla de carácter normal
    return KeyCode.from_char(part)


# ── Ratón ─────────────────────────────────────────────────────────────────────

def mouse_move(x: int, y: int) -> dict[str, Any]:
    if not _PYNPUT_OK:
        return {"stub": True, "action": "move", "x": x, "y": y}
    m = _MouseCtrl()
    m.position = (x, y)
    return {"moved_to": [x, y]}


def mouse_click(
    x: int, y: int, button: str = "left", count: int = 1
) -> dict[str, Any]:
    if not _PYNPUT_OK:
        return {"stub": True, "action": "click", "x": x, "y": y, "button": button}
    m = _MouseCtrl()
    m.position = (x, y)
    time.sleep(0.05)
    btn = Button.left if button in ("left", "izquierdo") else Button.right
    m.click(btn, count)
    return {"clicked": [x, y], "button": button, "count": count}


def mouse_double_click(x: int, y: int, button: str = "left") -> dict[str, Any]:
    return mouse_click(x, y, button=button, count=2)


def mouse_scroll(
    x: int, y: int, direction: str = "down", amount: int = 3
) -> dict[str, Any]:
    if not _PYNPUT_OK:
        return {"stub": True, "action": "scroll", "direction": direction, "amount": amount}
    m = _MouseCtrl()
    m.position = (x, y)
    dy = -amount if direction == "down" else amount
    m.scroll(0, dy)
    return {"scrolled": direction, "amount": amount, "at": [x, y]}


# ── Teclado ───────────────────────────────────────────────────────────────────

def keyboard_type(text: str) -> dict[str, Any]:
    """Escribe texto tal cual, carácter a carácter."""
    if not _PYNPUT_OK:
        return {"stub": True, "action": "type", "chars": len(text)}
    kb = _KbCtrl()
    kb.type(text)
    return {"typed_chars": len(text), "preview": text[:40] + ("…" if len(text) > 40 else "")}


def keyboard_press(key: str) -> dict[str, Any]:
    """Pulsa y suelta una tecla simple: 'enter', 'tab', 'escape', 'f5'…"""
    if not _PYNPUT_OK:
        return {"stub": True, "action": "press", "key": key}
    kb = _KbCtrl()
    k = _resolve_key(key)
    kb.press(k)
    kb.release(k)
    return {"pressed": key}


def keyboard_hotkey(keys: str) -> dict[str, Any]:
    """
    Pulsa una combinación de teclas: 'ctrl+a', 'ctrl+shift+t', 'alt+f4', etc.
    Las teclas se separan por '+'.
    """
    if not _PYNPUT_OK:
        return {"stub": True, "action": "hotkey", "keys": keys}
    kb = _KbCtrl()
    parts = [p.strip() for p in keys.split("+")]
    resolved = [_resolve_key(p) for p in parts]
    try:
        for k in resolved:
            kb.press(k)
        time.sleep(0.05)
    finally:
        for k in reversed(resolved):
            kb.release(k)
    return {"hotkey": keys}
