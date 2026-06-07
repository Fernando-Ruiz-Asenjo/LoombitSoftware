"""
windows_control.py — foco de ventana y UI Automation para Windows.

Jerarquía de automatización (más fiable primero):
  1. pywinauto — UI Automation tree completo, click_control por nombre/role.
  2. win32gui (pywin32) — foco de ventana cuando pywinauto no está disponible.
  3. ctypes puro — fallback mínimo, solo foco por hwnd.

open_url usa webbrowser.open que delega en el navegador predeterminado.
"""

from __future__ import annotations

import logging
import re
import webbrowser
from typing import Any

logger = logging.getLogger(__name__)

# ── Imports opcionales ────────────────────────────────────────────────────────

try:
    import pywinauto  # type: ignore  # noqa: F401

    _PYWINAUTO_OK = True
except Exception:
    _PYWINAUTO_OK = False
    logger.info("pywinauto no disponible — usando win32gui/ctypes como fallback")

try:
    import win32gui  # type: ignore
    import win32con  # type: ignore

    _WIN32_OK = True
except ImportError:
    _WIN32_OK = False
    logger.info("pywin32 no disponible — foco de ventana limitado a ctypes")


# ── URL ───────────────────────────────────────────────────────────────────────


def open_url(url: str) -> dict[str, Any]:
    """Abre una URL en el navegador predeterminado del sistema."""
    if not url.startswith(("http://", "https://")):
        return {"error": f"URL no válida (debe comenzar con http/https): {url!r}"}
    webbrowser.open(url)
    return {"opened_url": _redact_url(url)}


def _redact_url(url: str) -> str:
    """Redacta parámetros de query que puedan contener tokens."""
    return re.sub(r"([?&][^=]+=)[^&]+", r"\1***", url)


# ── Foco de ventana ───────────────────────────────────────────────────────────


def focus_window(process_name: str = "", title: str = "") -> dict[str, Any]:
    """
    Trae una ventana al frente.
    Intenta pywinauto primero, luego win32gui, luego ctypes.
    """
    if _PYWINAUTO_OK:
        return _focus_pywinauto(process_name=process_name, title=title)
    if _WIN32_OK:
        return _focus_win32(title=title, process_name=process_name)
    return _focus_ctypes(title=title)


def _focus_pywinauto(process_name: str, title: str) -> dict[str, Any]:
    try:
        kwargs: dict[str, Any] = {}
        if title:
            kwargs["title_re"] = f".*{re.escape(title)}.*"
        if process_name:
            kwargs["best_match"] = process_name

        # Busca ventana activa
        from pywinauto import Desktop  # type: ignore

        windows = Desktop(backend="uia").windows()
        for w in windows:
            try:
                wt = w.window_text()
                wp = w.process_id()
                match = True
                if title and title.lower() not in wt.lower():
                    match = False
                if process_name:
                    import psutil  # type: ignore

                    try:
                        pname = psutil.Process(wp).name().lower()
                        if process_name.lower() not in pname:
                            match = False
                    except Exception:
                        pass
                if match:
                    w.set_focus()
                    return {"focused": True, "window_title": wt, "backend": "pywinauto"}
            except Exception:
                continue
        return {"focused": False, "error": "No se encontró la ventana", "backend": "pywinauto"}
    except Exception as exc:
        logger.debug("pywinauto focus failed: %s", exc)
        if _WIN32_OK:
            return _focus_win32(title=title, process_name=process_name)
        return {"focused": False, "error": str(exc)}


def _focus_win32(title: str, process_name: str) -> dict[str, Any]:
    found: list[int] = []

    def _enum(hwnd: int, _: Any) -> None:
        if not win32gui.IsWindowVisible(hwnd):
            return
        t = win32gui.GetWindowText(hwnd)
        if title and title.lower() in t.lower():
            found.append(hwnd)
        elif not title and process_name:
            # Sin título, buscar por proceso (aproximado por clase de ventana)
            cls = win32gui.GetClassName(hwnd)
            if process_name.lower() in cls.lower():
                found.append(hwnd)

    win32gui.EnumWindows(_enum, None)
    if found:
        hwnd = found[0]
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
            return {
                "focused": True,
                "hwnd": hwnd,
                "window_title": win32gui.GetWindowText(hwnd),
                "backend": "win32gui",
            }
        except Exception as exc:
            return {"focused": False, "error": str(exc), "backend": "win32gui"}
    return {"focused": False, "error": "Ventana no encontrada", "backend": "win32gui"}


def _focus_ctypes(title: str) -> dict[str, Any]:
    """Último recurso: ctypes FindWindow."""
    import ctypes

    user32 = ctypes.windll.user32
    hwnd = user32.FindWindowW(None, title) if title else 0
    if hwnd:
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.SetForegroundWindow(hwnd)
        return {"focused": True, "hwnd": hwnd, "backend": "ctypes"}
    return {"focused": False, "error": "ctypes FindWindow no encontró ventana"}


# ── Inspección de controles UI Automation ────────────────────────────────────


def inspect_controls(process_name: str = "", title: str = "", limit: int = 40) -> dict[str, Any]:
    """
    Enumera los controles accesibles de la ventana indicada.
    Devuelve una lista de {name, control_type, automation_id, rect}.
    """
    if not _PYWINAUTO_OK:
        return {
            "controls": [],
            "error": "pywinauto no instalado — instala con: pip install pywinauto",
            "hint": "Sin pywinauto, usa coordenadas directas (click con x,y).",
        }
    try:
        from pywinauto import Desktop  # type: ignore

        windows = Desktop(backend="uia").windows()
        target = None
        for w in windows:
            try:
                wt = w.window_text()
                if title and title.lower() not in wt.lower():
                    continue
                if process_name:
                    import psutil  # type: ignore

                    pname = psutil.Process(w.process_id()).name().lower()
                    if process_name.lower() not in pname:
                        continue
                target = w
                break
            except Exception:
                continue

        if not target:
            return {"controls": [], "error": "Ventana no encontrada para inspeccionar"}

        controls = []
        for ctrl in target.descendants()[:limit]:
            try:
                name = ctrl.window_text()[:80]
                ctype = ctrl.element_info.control_type
                aid = ctrl.element_info.automation_id[:40]
                rect = ctrl.rectangle()
                controls.append(
                    {
                        "name": name,
                        "control_type": ctype,
                        "automation_id": aid,
                        "rect": {
                            "left": rect.left,
                            "top": rect.top,
                            "right": rect.right,
                            "bottom": rect.bottom,
                        },
                    }
                )
            except Exception:
                pass

        return {
            "controls": controls,
            "total_found": len(controls),
            "window_title": target.window_text(),
        }
    except Exception as exc:
        return {"controls": [], "error": str(exc)}


def click_control(
    name: str = "",
    automation_id: str = "",
    process_name: str = "",
    title: str = "",
) -> dict[str, Any]:
    """
    Hace clic en un control accesible buscando por nombre o automation_id.
    Más estable que coordenadas — usa UI Automation tree.
    """
    if not _PYWINAUTO_OK:
        return {
            "error": "pywinauto no instalado — usa click con coordenadas x,y",
            "stub": True,
        }
    try:
        from pywinauto import Desktop  # type: ignore

        windows = Desktop(backend="uia").windows()
        target = None
        for w in windows:
            try:
                wt = w.window_text()
                if title and title.lower() not in wt.lower():
                    continue
                if process_name:
                    import psutil  # type: ignore

                    pname = psutil.Process(w.process_id()).name().lower()
                    if process_name.lower() not in pname:
                        continue
                target = w
                break
            except Exception:
                continue

        if not target:
            return {"clicked": False, "error": "Ventana no encontrada"}

        ctrl = None
        for c in target.descendants():
            try:
                matches = True
                if name and name.lower() not in c.window_text().lower():
                    matches = False
                if automation_id and automation_id not in c.element_info.automation_id:
                    matches = False
                if matches and (name or automation_id):
                    ctrl = c
                    break
            except Exception:
                continue

        if not ctrl:
            return {
                "clicked": False,
                "error": f"Control no encontrado: name={name!r} aid={automation_id!r}",
            }

        ctrl.click_input()
        return {"clicked": True, "control_name": name or automation_id}
    except Exception as exc:
        return {"clicked": False, "error": str(exc)}


def click_accessibility(
    name: str = "",
    automation_id: str = "",
    window_title: str = "",
) -> dict[str, Any]:
    """
    Hace clic en un control accesible (UI Automation) por nombre o automation_id.

    Alias semántico de :func:`click_control` que filtra la ventana por
    `window_title`. Es la entrada que usa la tool `desktop_click_accessibility`.
    """
    if not name and not automation_id:
        return {"clicked": False, "error": "Indica name o automation_id"}
    return click_control(name=name, automation_id=automation_id, title=window_title)


# ── Espera de ventana ─────────────────────────────────────────────────────────


def _match_window_title(title: str) -> str | None:
    """Devuelve el texto de la primera ventana visible cuyo título contiene `title`."""
    needle = title.lower()

    if _PYWINAUTO_OK:
        try:
            from pywinauto import Desktop  # type: ignore

            for w in Desktop(backend="uia").windows():
                try:
                    wt = w.window_text()
                    if wt and needle in wt.lower():
                        return wt
                except Exception:
                    continue
        except Exception as exc:
            logger.debug("pywinauto wait_for_window falló: %s", exc)

    if _WIN32_OK:
        found: list[str] = []

        def _enum(hwnd: int, _: Any) -> None:
            if not win32gui.IsWindowVisible(hwnd):
                return
            t = win32gui.GetWindowText(hwnd)
            if t and needle in t.lower():
                found.append(t)

        try:
            win32gui.EnumWindows(_enum, None)
            if found:
                return found[0]
        except Exception:
            pass

    # Último recurso: ctypes (sólo coincidencia exacta del título).
    try:
        import ctypes

        if ctypes.windll.user32.FindWindowW(None, title):
            return title
    except Exception:
        pass

    return None


def wait_for_window(
    title: str,
    timeout: float = 10.0,
    poll_interval: float = 0.5,
) -> dict[str, Any]:
    """
    Espera hasta `timeout` segundos a que aparezca una ventana cuyo título
    contenga `title` (búsqueda case-insensitive por subcadena).

    Devuelve {found, window_title, waited_seconds}. No bloquea más de `timeout`.
    Útil tras abrir una app o lanzar un diálogo, antes de interactuar con él.
    """
    import time

    if not title:
        return {"found": False, "error": "title vacío"}

    timeout = max(0.0, float(timeout))
    poll_interval = max(0.05, float(poll_interval))
    deadline = time.monotonic() + timeout
    waited = 0.0

    while True:
        matched = _match_window_title(title)
        if matched is not None:
            return {"found": True, "window_title": matched, "waited_seconds": round(waited, 2)}
        if time.monotonic() >= deadline:
            return {
                "found": False,
                "waited_seconds": round(waited, 2),
                "error": f"La ventana {title!r} no apareció en {timeout:g}s",
            }
        time.sleep(poll_interval)
        waited += poll_interval


# ── Snapshot de accesibilidad (UIA) — accesibilidad-primero ───────────────────

# Tipos de control accionables (clic/edición). El agente debe preferir actuar
# sobre estos por name/automation_id (click_accessibility) antes que por píxeles.
_INTERACTIVE_TYPES = {
    "Button",
    "SplitButton",
    "Edit",
    "CheckBox",
    "RadioButton",
    "ComboBox",
    "ListItem",
    "MenuItem",
    "Hyperlink",
    "Tab",
    "TabItem",
    "TreeItem",
    "Slider",
    "Spinner",
}


def _control_value(ctrl: Any) -> str:
    """Extrae el valor textual de un control (campos, combos) de forma tolerante."""
    for getter in ("get_value", "get_line"):
        try:
            fn = getattr(ctrl, getter, None)
            if callable(fn):
                val = fn()
                if val:
                    return str(val)
        except Exception:
            pass
    try:
        legacy = ctrl.legacy_properties()  # type: ignore[attr-defined]
        if isinstance(legacy, dict) and legacy.get("Value"):
            return str(legacy["Value"])
    except Exception:
        pass
    return ""


def _describe_control(ctrl: Any) -> dict[str, Any] | None:
    """
    Describe un control UIA en forma compacta y accionable para el agente:
    {name, control_type, automation_id, center:[x,y], enabled, offscreen, value?}.

    Devuelve None si el control no puede leerse.
    """
    try:
        info = ctrl.element_info
        name = (ctrl.window_text() or "")[:80]
        ctype = str(info.control_type or "")
        aid = str(info.automation_id or "")[:40]
        rect = ctrl.rectangle()
        width = rect.right - rect.left
        height = rect.bottom - rect.top
        item: dict[str, Any] = {
            "name": name,
            "control_type": ctype,
            "automation_id": aid,
            "center": [(rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2],
            "enabled": bool(getattr(info, "enabled", True)),
            "offscreen": width <= 0 or height <= 0,
        }
        value = _control_value(ctrl)
        if value:
            item["value"] = value[:120]
        return item
    except Exception:
        return None


def _is_actionable(desc: dict[str, Any]) -> bool:
    """True si el control es de un tipo accionable (clic/edición)."""
    return desc.get("control_type") in _INTERACTIVE_TYPES


def _find_uia_window(process_name: str, title: str) -> Any:
    """Primera ventana UIA que casa por título y/o proceso. Requiere pywinauto."""
    from pywinauto import Desktop  # type: ignore

    for w in Desktop(backend="uia").windows():
        try:
            wt = w.window_text()
            if title and title.lower() not in wt.lower():
                continue
            if process_name:
                import psutil  # type: ignore

                pname = psutil.Process(w.process_id()).name().lower()
                if process_name.lower() not in pname:
                    continue
            return w
        except Exception:
            continue
    return None


def ui_snapshot(
    process_name: str = "",
    title: str = "",
    limit: int = 80,
    interactive_only: bool = True,
) -> dict[str, Any]:
    """
    Lee el árbol de accesibilidad (UIA) de la ventana objetivo y devuelve una
    lista compacta de controles **accionables** (con su centro para clic de
    respaldo). Es la vía preferente: más fiable que los píxeles y sin alucinar.

    Si pywinauto no está disponible, lo indica para que el agente caiga a la
    captura + coordenadas.
    """
    if not _PYWINAUTO_OK:
        return {
            "controls": [],
            "error": "pywinauto no instalado",
            "hint": "Sin UIA: usa screenshot + click por coordenadas.",
        }
    try:
        target = _find_uia_window(process_name, title)
        if target is None:
            return {"controls": [], "error": "Ventana no encontrada"}

        controls: list[dict[str, Any]] = []
        for ctrl in target.descendants():
            desc = _describe_control(ctrl)
            if desc is None:
                continue
            if interactive_only and not _is_actionable(desc):
                continue
            controls.append(desc)
            if len(controls) >= limit:
                break

        return {
            "controls": controls,
            "total": len(controls),
            "window_title": target.window_text(),
            "interactive_only": interactive_only,
        }
    except Exception as exc:
        return {"controls": [], "error": str(exc)}
