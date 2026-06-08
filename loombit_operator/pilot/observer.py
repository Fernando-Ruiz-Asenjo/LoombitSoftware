"""
observer.py — Skill W Pilot: observación SEMÁNTICA de la actividad para aprender los procesos.

Registra QUÉ aplicación y ventana usa el usuario (app + título + proceso) para aprender sus procesos
diarios y proponer automatizaciones (Fábrica de Skills). Local y OPT-IN (apagado por defecto).

LÍMITE DURO DE PRIVACIDAD/SEGURIDAD (no negociable):
  - NO captura pulsaciones de teclado (sería un keylogger → tus contraseñas y banca).
  - NO captura el contenido de la pantalla ni de campos seguros/contraseña.
  - Solo el FLUJO de aplicaciones (semántico). El usuario lo activa, lo ve y lo borra cuando quiera.

El keylogging crudo no solo es peligroso: es mal aprendizaje (ruido). La señal útil para automatizar
es la secuencia de apps/acciones, no las teclas. Ver `docs/FABRICA_DE_SKILLS.md`.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def foreground_activity() -> dict[str, Any]:
    """App + título de la ventana en primer plano (best-effort; campos vacíos fuera de Windows).

    NO incluye teclas ni contenido de pantalla — solo identidad de la ventana activa."""
    muestra: dict[str, Any] = {"ts": datetime.now(UTC).isoformat(), "app": "", "title": ""}
    try:
        import win32gui
        import win32process

        hwnd = win32gui.GetForegroundWindow()
        muestra["title"] = (win32gui.GetWindowText(hwnd) or "")[:120]
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        try:
            import psutil

            muestra["app"] = psutil.Process(pid).name()
        except Exception:
            pass
    except Exception:
        pass
    return muestra


def registrar_actividad(base_dir: Path | None = None) -> dict[str, Any]:
    """Anexa una muestra de actividad al log local (jsonl) y la devuelve. Solo semántico."""
    muestra = foreground_activity()
    carpeta = base_dir or Path("runtime/local/observer")
    carpeta.mkdir(parents=True, exist_ok=True)
    with open(carpeta / "activity.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(muestra, ensure_ascii=False) + "\n")
    return muestra


def resumen_procesos(base_dir: Path | None = None, top: int = 8) -> list[dict[str, Any]]:
    """Resume el log: qué apps usas más (para aprender tus procesos diarios). Local, sin teclas."""
    from collections import Counter

    carpeta = base_dir or Path("runtime/local/observer")
    ruta = carpeta / "activity.jsonl"
    if not ruta.exists():
        return []
    cnt: Counter = Counter()
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        try:
            app = json.loads(linea).get("app", "")
        except json.JSONDecodeError:
            continue
        if app:
            cnt[app] += 1
    return [{"app": app, "muestras": n} for app, n in cnt.most_common(top)]
