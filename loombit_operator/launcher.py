"""
Loombit Operator — Launcher con icono en la bandeja del sistema.

Arranca el servidor FastAPI (uvicorn) en un hilo daemon, abre la UI en el navegador
y muestra un icono en la bandeja de Windows con menú de control.

Diseñado para ser **sólido y diagnosticable**:
- Escribe SIEMPRE a `runtime/local/launcher.log` (con `pythonw` no hay consola; sin este
  log, un fallo sería invisible — esa era la causa de "se rompe y no sé por qué").
- Hace *preflight* de las dependencias y del código antes de arrancar; si algo falta,
  muestra un MessageBox claro en vez de morir en silencio.
- Si el puerto ya está en uso, abre la UI existente en vez de reventar.

Uso:
    python -m loombit_operator.launcher     (consola, ves logs en vivo)
    pythonw -m loombit_operator.launcher    (sin consola; logs en launcher.log)
    (o vía el acceso directo del escritorio → scripts/start_loombit.ps1)
"""

from __future__ import annotations

import logging
import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

# ── Constantes ────────────────────────────────────────────────────────────────
HOST = "127.0.0.1"
PORT = 8787
UI_URL = f"http://{HOST}:{PORT}"

logger = logging.getLogger("loombit.launcher")
_LOG_FMT = "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s"


# ── Rutas (funciona tanto en desarrollo como en exe congelado) ────────────────


def _base_dir() -> Path:
    """Directorio raíz del proyecto/proceso (donde viven `static/` y `runtime/`)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent.parent


def _asset(name: str) -> Path:
    """Ruta a un asset (funciona en desarrollo y en bundle PyInstaller)."""
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        base = Path(__file__).parent
    return base / "assets" / name


def _log_path(base_dir: Path) -> Path:
    return base_dir / "runtime" / "local" / "launcher.log"


# ── Logging y errores visibles ────────────────────────────────────────────────


def _setup_logging(base_dir: Path) -> None:
    """Log a consola (si la hay) y SIEMPRE a fichero — clave con `pythonw` (sin consola)."""
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    fmt = logging.Formatter(_LOG_FMT)
    root.addHandler(logging.StreamHandler())
    try:
        path = _log_path(base_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(path, encoding="utf-8")
        fh.setFormatter(fmt)
        root.addHandler(fh)
    except OSError as exc:  # nunca debe impedir el arranque
        logger.warning("No se pudo abrir el log de fichero: %s", exc)
    for h in root.handlers:
        h.setFormatter(fmt)


def _fatal(message: str) -> None:
    """Registra un error fatal y lo muestra en un MessageBox (sin dependencias extra)."""
    logger.error("FATAL: %s", message)
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(  # type: ignore[attr-defined]
            0, message, "Loombit Operator — error", 0x10  # MB_ICONERROR
        )
    except Exception:
        pass


# ── Comprobación de puerto ────────────────────────────────────────────────────


def _port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((HOST, port)) != 0


def _wait_server_ready(port: int, timeout: float = 20.0) -> bool:
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        if not _port_free(port):
            return True
        time.sleep(0.2)
    return False


# ── Servidor uvicorn en hilo ──────────────────────────────────────────────────

_server: object = None  # uvicorn.Server


def _start_server() -> None:
    """Arranca uvicorn (el cwd ya se fijó en main). Cualquier fallo va al log."""
    global _server
    try:
        import uvicorn

        config = uvicorn.Config(
            "loombit_operator.main:app",
            host=HOST,
            port=PORT,
            log_level="info",
            access_log=False,
            # log_config=None: con `pythonw` no hay stdout y el formatter de color de uvicorn
            # crashea (sys.stdout.isatty sobre None). Usamos nuestro logging (root + fichero).
            log_config=None,
        )
        _server = uvicorn.Server(config)
        _server.run()
    except Exception:
        logger.exception("El servidor uvicorn se detuvo con error")


# ── Icono de la bandeja ───────────────────────────────────────────────────────


def _load_tray_icon():
    """Carga el icono desde assets/ o genera uno mínimo si no existe."""
    from PIL import Image

    ico_path = _asset("loombit.ico")
    if ico_path.exists():
        try:
            return Image.open(ico_path)
        except Exception:
            pass
    return Image.new("RGB", (64, 64), (0, 210, 175))  # fallback teal


def _make_tray_menu(base_dir: Path):
    import pystray

    def on_open(icon, item):
        webbrowser.open(UI_URL)

    def on_stop(icon, item):
        global _server
        logger.info("Deteniendo Loombit Operator...")
        if _server and hasattr(_server, "should_exit"):
            _server.should_exit = True  # type: ignore[attr-defined]
        icon.stop()

    def on_logs(icon, item):
        path = _log_path(base_dir)
        if path.exists():
            os.startfile(str(path))  # noqa: S606 — abrir el log local del usuario
        else:
            webbrowser.open(f"{UI_URL}/health")

    return pystray.Menu(
        pystray.MenuItem(f"Loombit Operator  ·  :{PORT}", None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Abrir UI  ↗", on_open, default=True),
        pystray.MenuItem("Abrir logs", on_logs),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Detener", on_stop),
    )


# ── Main ──────────────────────────────────────────────────────────────────────


def _ensure_std_streams() -> None:
    """Con `pythonw` (sin consola) sys.stdout/stderr son None; cualquier librería que asuma
    que existen (uvicorn, prints) crashea. Los redirige a un sumidero seguro."""
    devnull = open(os.devnull, "w")  # noqa: SIM115 — vive lo que dure el proceso
    if sys.stdout is None:
        sys.stdout = devnull
    if sys.stderr is None:
        sys.stderr = devnull


def main() -> None:
    _ensure_std_streams()
    base_dir = _base_dir()
    _setup_logging(base_dir)
    logger.info("Loombit Operator — base dir: %s — python: %s", base_dir, sys.executable)

    # cwd al raíz: `static/` y `runtime/` se resuelven igual desde cualquier acceso directo.
    try:
        os.chdir(base_dir)
    except OSError as exc:
        _fatal(f"No se pudo entrar al directorio del proyecto:\n{base_dir}\n\n{exc}")
        return

    # Preflight: carga uvicorn y la app ANTES de arrancar; si falla, error visible.
    try:
        import uvicorn  # noqa: F401
        from loombit_operator.main import app  # noqa: F401
    except Exception as exc:
        _fatal(
            "Loombit no pudo cargar (dependencias o código). Revisa el log:\n"
            f"{_log_path(base_dir)}\n\n{exc!r}"
        )
        logger.exception("Fallo en el preflight de carga")
        return

    # Si ya hay una instancia, abre la UI existente y sal (instancia única).
    if not _port_free(PORT):
        logger.info("Puerto %d ya en uso — abriendo la UI existente", PORT)
        webbrowser.open(UI_URL)
        return

    threading.Thread(target=_start_server, daemon=True, name="uvicorn").start()

    logger.info("Esperando al servidor en %s ...", UI_URL)
    if _wait_server_ready(PORT):
        logger.info("Servidor listo en %s", UI_URL)
        webbrowser.open(UI_URL)
    else:
        _fatal(
            "El servidor no respondió a tiempo. Puede que falte una dependencia "
            f"o haya un error de arranque. Revisa el log:\n{_log_path(base_dir)}"
        )
        return

    # Icono en la bandeja. Sin pystray/PIL: el servidor sigue vivo en primer plano.
    try:
        import pystray  # noqa: F401
        from PIL import Image  # noqa: F401
    except ImportError:
        logger.warning("pystray/Pillow no disponibles: sin icono de bandeja (servidor activo).")
        try:
            threading.Event().wait()  # mantener el proceso vivo
        except KeyboardInterrupt:
            pass
        return

    try:
        import pystray

        icon = pystray.Icon(
            name="Loombit",
            icon=_load_tray_icon(),
            title="Loombit Operator",
            menu=_make_tray_menu(base_dir),
        )
        logger.info("Icono en bandeja activo. Click derecho para el menú.")
        icon.run()  # bloquea hasta on_stop → icon.stop()
    except Exception:
        logger.exception("El icono de bandeja falló; mantengo el servidor vivo")
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            pass
        return

    logger.info("Loombit Operator detenido.")


if __name__ == "__main__":
    main()
