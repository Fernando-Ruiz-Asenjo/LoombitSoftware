"""
overlay_manager.py — mantiene la señal visible del Pilot mientras el Pilot controla el escritorio.

Las acciones del Pilot (tools `desktop_*` del agente vía `/computer-use/*`, o `execute_sequence`)
ocurren DENTRO del servidor uvicorn, que no pinta tkinter de forma fiable desde un hilo de
trabajo. Por eso el halo corre en su PROPIO proceso (`overlay_proc`), y aquí solo:

  - `touch()`: enciende el proceso del halo si no estaba y refresca un fichero *keepalive*.
  - el proceso del halo se cierra SOLO cuando el keepalive caduca (`IDLE_TIMEOUT` sin acciones).

Así, mientras el agente actúa (clic/teclea), el usuario VE "LOOMBIT PILOTANDO" con los colores
de Loombit; cuando el agente termina, el halo desaparece solo. Queda claro que **pilota Loombit**.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from pathlib import Path

# Segundos sin acciones tras los cuales el proceso del halo se cierra (fin de "sesión").
IDLE_TIMEOUT = 5.0

# Guarda para tests/CI: con LOOMBIT_PILOT_OVERLAY_OFF=1, `touch()` no lanza nada.
_DISABLED_ENV = "LOOMBIT_PILOT_OVERLAY_OFF"

_KEEPALIVE = (
    Path(os.environ.get("TEMP", os.environ.get("TMP", "."))) / "loombit_pilot_overlay.alive"
)

_lock = threading.Lock()
_proc: subprocess.Popen | None = None

# Sesión de pilotaje: mientras está activa, un heartbeat refresca el keepalive cada
# segundo → el halo se mantiene PERSISTENTE durante todo el run del agente (aunque el
# 14B tarde entre pasos), no parpadea por acción suelta.
_session_active = False
_heartbeat: threading.Thread | None = None


def _disabled() -> bool:
    return os.environ.get(_DISABLED_ENV) == "1"


def _spawn() -> subprocess.Popen:
    creationflags = 0
    if sys.platform.startswith("win"):
        creationflags = 0x08000000  # CREATE_NO_WINDOW: sin consola
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "loombit_operator.pilot.overlay_proc",
            str(_KEEPALIVE),
            str(IDLE_TIMEOUT),
            "LOOMBIT PILOTANDO",
        ],
        creationflags=creationflags,
    )


def touch() -> None:
    """Señala actividad del Pilot: refresca el keepalive y enciende el halo si no estaba."""
    global _proc
    if _disabled():
        return
    with _lock:
        try:
            _KEEPALIVE.parent.mkdir(parents=True, exist_ok=True)
            _KEEPALIVE.touch()  # crea/actualiza mtime = ahora
        except Exception:
            return
        if _proc is None or _proc.poll() is not None:
            try:
                _proc = _spawn()
            except Exception:
                _proc = None


def start_session() -> None:
    """Abre una sesión de pilotaje: el halo se mantiene encendido (heartbeat) hasta `stop_session`."""
    global _session_active, _heartbeat
    if _disabled():
        return
    with _lock:
        _session_active = True
        if _heartbeat is None or not _heartbeat.is_alive():
            _heartbeat = threading.Thread(target=_beat, daemon=True)
            _heartbeat.start()
    touch()  # enciende ya, sin esperar al primer latido


def _beat() -> None:
    while True:
        with _lock:
            active = _session_active
        if not active:
            return
        touch()
        time.sleep(1.0)


def stop_session() -> None:
    """Cierra la sesión de pilotaje: el halo se apaga solo tras IDLE_TIMEOUT sin latidos."""
    global _session_active
    with _lock:
        _session_active = False


def is_active() -> bool:
    """True si el proceso del halo está vivo ahora mismo."""
    with _lock:
        return _proc is not None and _proc.poll() is None


def force_stop() -> None:
    """Apaga el halo de inmediato (limpieza/tests): borra el keepalive y termina el proceso."""
    global _proc, _session_active
    with _lock:
        _session_active = False
        try:
            if _KEEPALIVE.exists():
                _KEEPALIVE.unlink()
        except Exception:
            pass
        if _proc is not None and _proc.poll() is None:
            try:
                _proc.terminate()
            except Exception:
                pass
        _proc = None
