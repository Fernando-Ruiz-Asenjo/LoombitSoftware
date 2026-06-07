"""
Loombit Operator — Launcher con icono en bandeja del sistema.

Arranca el servidor FastAPI (uvicorn) en un hilo daemon y muestra
un icono en la bandeja de Windows con menú de control.

Uso:
    python -m loombit_operator.launcher
    (o desde el exe compilado con PyInstaller)
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger("loombit.launcher")


# ── Rutas (funciona tanto en desarrollo como en exe congelado) ────────────────


def _base_dir() -> Path:
    """Directorio base del exe/proceso."""
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


# ── Comprobación de puerto libre ──────────────────────────────────────────────


def _port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((HOST, port)) != 0


def _wait_server_ready(port: int, timeout: float = 15.0) -> bool:
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        if not _port_free(port):
            return True
        time.sleep(0.2)
    return False


# ── Servidor uvicorn en hilo ──────────────────────────────────────────────────

_server: object = None  # uvicorn.Server


def _start_server(base_dir: Path) -> None:
    """Arranca uvicorn en un hilo daemon. Cambia cwd al directorio base."""
    global _server
    os.chdir(base_dir)

    try:
        import uvicorn
        from loombit_operator.main import app  # noqa: F401 — importado para registrar routers
    except Exception as exc:
        logger.exception("Error importando app: %s", exc)
        return

    config = uvicorn.Config(
        "loombit_operator.main:app",
        host=HOST,
        port=PORT,
        log_level="info",
        access_log=False,
    )
    _server = uvicorn.Server(config)
    try:
        _server.run()
    except Exception as exc:
        logger.exception("Error en uvicorn: %s", exc)


# ── Icono de la bandeja ───────────────────────────────────────────────────────


def _load_tray_icon():
    """Carga el icono desde assets/ o genera uno mínimo si no existe."""
    try:
        from PIL import Image

        ico_path = _asset("loombit.ico")
        if ico_path.exists():
            return Image.open(ico_path)
        # Fallback: cuadrado teal si no existe el fichero
        img = Image.new("RGB", (64, 64), (0, 210, 175))
        return img
    except Exception:
        from PIL import Image

        return Image.new("RGB", (64, 64), (0, 210, 175))


def _make_tray_menu(icon_ref: list):
    """Construye el menú de la bandeja."""
    import pystray

    def on_open(icon, item):
        webbrowser.open(UI_URL)

    def on_stop(icon, item):
        global _server
        logger.info("Deteniendo Loombit Operator...")
        if _server and hasattr(_server, "should_exit"):
            _server.should_exit = True
        icon.stop()

    def on_logs(icon, item):
        log_path = _base_dir() / "runtime" / "local" / "loombit.log"
        if log_path.exists():
            os.startfile(str(log_path))
        else:
            webbrowser.open(f"{UI_URL}/health")

    return pystray.Menu(
        pystray.MenuItem(
            f"Loombit Operator  ·  :{PORT}",
            None,
            enabled=False,
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Abrir UI  ↗", on_open, default=True),
        pystray.MenuItem("Abrir logs", on_logs),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Detener", on_stop),
    )


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    base_dir = _base_dir()
    logger.info("Loombit Operator — base dir: %s", base_dir)

    # Comprobar que el puerto no está ya ocupado
    if not _port_free(PORT):
        logger.warning("Puerto %d ya en uso — abriendo UI existente", PORT)
        webbrowser.open(UI_URL)
        return

    # Arrancar servidor en hilo daemon
    server_thread = threading.Thread(
        target=_start_server,
        args=(base_dir,),
        daemon=True,
        name="uvicorn",
    )
    server_thread.start()

    # Esperar hasta que el servidor esté listo (máx 15s)
    logger.info("Esperando servidor en puerto %d...", PORT)
    if _wait_server_ready(PORT, timeout=15.0):
        logger.info("Servidor listo en %s", UI_URL)
    else:
        logger.warning("El servidor no respondió en 15s — continuando de todas formas")

    # Abrir UI en el navegador al arrancar
    webbrowser.open(UI_URL)

    # Mostrar icono en la bandeja
    try:
        import pystray
    except ImportError:
        logger.error("pystray no instalado. Ejecuta: pip install pystray")
        # Fallback: mantener el hilo del servidor vivo
        try:
            server_thread.join()
        except KeyboardInterrupt:
            pass
        return

    icon_img = _load_tray_icon()
    icon_ref: list = []
    menu = _make_tray_menu(icon_ref)

    icon = pystray.Icon(
        name="Loombit",
        icon=icon_img,
        title="Loombit Operator",
        menu=menu,
    )
    icon_ref.append(icon)

    logger.info("Icono en bandeja activo. Click derecho para el menú.")
    icon.run()  # bloquea hasta que se llama icon.stop()

    logger.info("Loombit Operator detenido.")


if __name__ == "__main__":
    main()
