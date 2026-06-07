"""
input_control.py - raton y teclado via pynput.

Primitivas de bajo nivel: mouse y teclado completos.
Requiere: pynput>=1.7.6
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

try:
    from pynput.mouse import Button, Controller as _MouseCtrl  # type: ignore
    from pynput.keyboard import Controller as _KbCtrl, Key, KeyCode  # type: ignore

    _PYNPUT_OK = True
except ImportError:
    _PYNPUT_OK = False
    logger.warning("pynput no instalado - input_control en modo stub")

_KEY_MAP: dict[str, Any] = {}


def _build_key_map() -> None:
    if not _PYNPUT_OK:
        return
    global _KEY_MAP
    _KEY_MAP = {
        "ctrl": Key.ctrl,
        "control": Key.ctrl,
        "shift": Key.shift,
        "alt": Key.alt,
        "win": Key.cmd,
        "cmd": Key.cmd,
        "super": Key.cmd,
        "enter": Key.enter,
        "return": Key.enter,
        "tab": Key.tab,
        "escape": Key.esc,
        "esc": Key.esc,
        "backspace": Key.backspace,
        "delete": Key.delete,
        "del": Key.delete,
        "space": Key.space,
        "up": Key.up,
        "down": Key.down,
        "left": Key.left,
        "right": Key.right,
        "home": Key.home,
        "end": Key.end,
        "page_up": Key.page_up,
        "pageup": Key.page_up,
        "page_down": Key.page_down,
        "pagedown": Key.page_down,
        "insert": Key.insert,
        "f1": Key.f1,
        "f2": Key.f2,
        "f3": Key.f3,
        "f4": Key.f4,
        "f5": Key.f5,
        "f6": Key.f6,
        "f7": Key.f7,
        "f8": Key.f8,
        "f9": Key.f9,
        "f10": Key.f10,
        "f11": Key.f11,
        "f12": Key.f12,
        "print_screen": Key.print_screen,
        "caps_lock": Key.caps_lock,
        "num_lock": Key.num_lock,
    }


_build_key_map()


def _resolve_key(part: str) -> Any:
    lo = part.lower().strip()
    if lo in _KEY_MAP:
        return _KEY_MAP[lo]
    return KeyCode.from_char(part)


# Mouse


def mouse_move(x: int, y: int) -> dict[str, Any]:
    if not _PYNPUT_OK:
        return {"stub": True, "action": "move", "x": x, "y": y}
    m = _MouseCtrl()
    m.position = (x, y)
    return {"moved_to": [x, y]}


def mouse_click(x: int, y: int, button: str = "left", count: int = 1) -> dict[str, Any]:
    if not _PYNPUT_OK:
        return {"stub": True, "action": "click", "x": x, "y": y}
    m = _MouseCtrl()
    m.position = (x, y)
    time.sleep(0.05)
    btn = Button.left if button in ("left", "izquierdo") else Button.right
    m.click(btn, count)
    return {"clicked": [x, y], "button": button, "count": count}


def mouse_double_click(x: int, y: int, button: str = "left") -> dict[str, Any]:
    return mouse_click(x, y, button=button, count=2)


def mouse_scroll(x: int, y: int, direction: str = "down", amount: int = 3) -> dict[str, Any]:
    if not _PYNPUT_OK:
        return {"stub": True, "action": "scroll"}
    m = _MouseCtrl()
    m.position = (x, y)
    dy = -amount if direction == "down" else amount
    m.scroll(0, dy)
    return {"scrolled": direction, "amount": amount, "at": [x, y]}


def mouse_drag(
    x1: int, y1: int, x2: int, y2: int, button: str = "left", duration: float = 0.3
) -> dict[str, Any]:
    if not _PYNPUT_OK:
        return {"stub": True, "action": "drag"}
    import math

    m = _MouseCtrl()
    btn = Button.left if button in ("left", "izquierdo") else Button.right
    m.position = (x1, y1)
    time.sleep(0.05)
    m.press(btn)
    steps = max(10, int(math.hypot(x2 - x1, y2 - y1) / 10))
    delay = duration / steps
    for i in range(1, steps + 1):
        t = i / steps
        m.position = (int(x1 + (x2 - x1) * t), int(y1 + (y2 - y1) * t))
        time.sleep(delay)
    m.release(btn)
    return {"dragged": {"from": [x1, y1], "to": [x2, y2]}}


def mouse_button_down(x: int, y: int, button: str = "left") -> dict[str, Any]:
    if not _PYNPUT_OK:
        return {"stub": True, "action": "mouse_down"}
    m = _MouseCtrl()
    m.position = (x, y)
    btn = Button.left if button in ("left", "izquierdo") else Button.right
    m.press(btn)
    return {"mouse_down": [x, y], "button": button}


def mouse_button_up(x: int, y: int, button: str = "left") -> dict[str, Any]:
    if not _PYNPUT_OK:
        return {"stub": True, "action": "mouse_up"}
    m = _MouseCtrl()
    m.position = (x, y)
    btn = Button.left if button in ("left", "izquierdo") else Button.right
    m.release(btn)
    return {"mouse_up": [x, y], "button": button}


def cursor_position() -> dict[str, Any]:
    if not _PYNPUT_OK:
        return {"stub": True, "x": 0, "y": 0}
    m = _MouseCtrl()
    x, y = m.position
    return {"x": x, "y": y}


# Teclado


def _should_use_clipboard(text: str) -> bool:
    """
    True si conviene escribir vía portapapeles en vez de tecla a tecla.

    `pynput.type()` es poco fiable con caracteres no-ASCII (acentos, ñ, €, ¿, ¡)
    porque depende del layout de teclado activo. Para texto con no-ASCII, saltos
    de línea o tabuladores, el pegado por portapapeles es exacto.
    """
    if not text:
        return False
    if "\n" in text or "\t" in text:
        return True
    return any(ord(ch) > 127 for ch in text)


def _type_via_clipboard(text: str) -> dict[str, Any] | None:
    """
    Escribe `text` pegándolo con Ctrl+V y restaura el portapapeles anterior.
    Devuelve None si el portapapeles no está disponible (para caer a pynput).
    """
    backup = clipboard_read().get("clipboard")
    written = clipboard_write(text)
    if "error" in written:
        return None
    keyboard_hotkey("ctrl+v")
    time.sleep(0.05)
    if isinstance(backup, str) and backup:
        clipboard_write(backup)  # cortesía: no pisar lo que tuviera el usuario
    return {"typed_chars": len(text), "preview": text[:40], "method": "clipboard"}


def keyboard_type(text: str, use_clipboard: bool | None = None) -> dict[str, Any]:
    if not _PYNPUT_OK:
        return {"stub": True, "action": "type", "chars": len(text)}
    if use_clipboard is None:
        use_clipboard = _should_use_clipboard(text)
    if use_clipboard:
        clip_result = _type_via_clipboard(text)
        if clip_result is not None:
            return clip_result
        # Si el portapapeles falla, caer al tecleo directo.
    kb = _KbCtrl()
    kb.type(text)
    return {"typed_chars": len(text), "preview": text[:40], "method": "pynput"}


def keyboard_press(key: str) -> dict[str, Any]:
    if not _PYNPUT_OK:
        return {"stub": True, "action": "press", "key": key}
    kb = _KbCtrl()
    k = _resolve_key(key)
    kb.press(k)
    kb.release(k)
    return {"pressed": key}


def keyboard_hotkey(keys: str) -> dict[str, Any]:
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


def keyboard_hold_press(key: str) -> dict[str, Any]:
    if not _PYNPUT_OK:
        return {"stub": True, "action": "hold_press", "key": key}
    _KbCtrl().press(_resolve_key(key))
    return {"holding": key}


def keyboard_hold_release(key: str) -> dict[str, Any]:
    if not _PYNPUT_OK:
        return {"stub": True, "action": "hold_release", "key": key}
    _KbCtrl().release(_resolve_key(key))
    return {"released": key}


# Portapapeles


def clipboard_read() -> dict[str, Any]:
    try:
        import pyperclip  # type: ignore

        text = pyperclip.paste()
        return {"clipboard": text, "length": len(text)}
    except ImportError:
        pass
    try:
        import win32clipboard  # type: ignore

        win32clipboard.OpenClipboard()
        try:
            text = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
        except Exception:
            text = ""
        finally:
            win32clipboard.CloseClipboard()
        return {"clipboard": text, "length": len(text)}
    except Exception as exc:
        return {"error": f"clipboard read failed: {exc}"}


def clipboard_write(text: str) -> dict[str, Any]:
    try:
        import pyperclip  # type: ignore

        pyperclip.copy(text)
        return {"written": len(text)}
    except ImportError:
        pass
    try:
        import win32clipboard  # type: ignore

        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT, text)
        finally:
            win32clipboard.CloseClipboard()
        return {"written": len(text)}
    except Exception as exc:
        return {"error": f"clipboard write failed: {exc}"}


# Aplicaciones


def open_application(app_name: str) -> dict[str, Any]:
    import subprocess

    try:
        subprocess.Popen(app_name, shell=True)
        return {"launched": app_name}
    except Exception as exc:
        return {"error": f"launch failed: {exc}"}
