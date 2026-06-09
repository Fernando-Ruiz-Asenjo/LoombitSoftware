"""Punto de entrada FastAPI. Solo crea la app y monta routers (anti-monolito)."""

from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path


def _patch_pywin32() -> None:
    """
    Asegura que pywin32 (instalado en user site-packages) sea importable por
    el proceso servidor, que puede no incluir user site-packages en sys.path.

    pywin32 requiere tres cosas:
      1. user_site-packages en sys.path  (para importar pywinauto, etc.)
      2. user_site-packages/win32 en sys.path  (para importar win32api.pyd)
      3. user_site-packages/pywin32_system32 en DLL search path (para pywintypes.dll)
    """
    try:
        import site

        # Directorios candidatos (user primero, luego system)
        candidates: list[Path] = []
        user_sp = site.getusersitepackages()
        if user_sp:
            candidates.append(Path(user_sp))
        if hasattr(site, "getsitepackages"):
            for sp in site.getsitepackages():
                candidates.append(Path(sp))

        for base in candidates:
            if not base.is_dir():
                continue

            # 1+2: Anadir base y subdirectorios win32 a sys.path
            for sub_rel in ("", "win32", "win32/lib", "Pythonwin"):
                p = base / sub_rel if sub_rel else base
                if p.is_dir() and str(p) not in sys.path:
                    sys.path.insert(1, str(p))

            # 3: Anadir directorios DLL al search path del proceso
            for dll_sub in ("pywin32_system32", "win32"):
                dll_dir = base / dll_sub
                if dll_dir.is_dir():
                    try:
                        os.add_dll_directory(str(dll_dir))
                    except (AttributeError, OSError):
                        # os.add_dll_directory solo existe en Windows Python 3.8+
                        # Si falla, aniadir al PATH como fallback
                        os.environ["PATH"] = str(dll_dir) + os.pathsep + os.environ.get("PATH", "")

            # Verificar que funciona despues de las modificaciones
            try:
                import importlib

                if importlib.util.find_spec("win32api") is not None:
                    return  # Exito: win32api es importable
            except Exception:
                pass

    except Exception:
        pass


_patch_pywin32()

# El Pilot necesita coordenadas a píxeles reales: activar DPI-awareness ya, antes
# de servir, para que captura y clic estén alineados en pantallas con escalado.
from .pilot.system import enable_dpi_awareness  # noqa: E402

enable_dpi_awareness()
# ─────────────────────────────────────────────────────────────────────────────

from fastapi import FastAPI  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from .config import get_settings  # noqa: E402
from .routers import (  # noqa: E402
    agent,
    computer,
    conciliacion,
    credentials,
    cuentas,
    docs,
    entregable,
    fabrica,
    fiscal,
    galaxia,
    health,
    home,
    mcp,
    pilot,
    rag,
    routines,
    skill_blanca_actions,
    skill_blanca_oauth,
    telar,
    ui,
)

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Arranca el daemon de Routines si está habilitado (opt-in por config)."""
    settings = get_settings()

    # F8 — al arrancar, sanea los runs huérfanos (quedaron "running" tras un reinicio).
    try:
        from .agent.run import AgentStore

        n = AgentStore().sweep_orphans()
        if n:
            import logging

            logging.getLogger("loombit").info("Saneados %d runs huérfanos al arrancar", n)
    except Exception:
        pass

    # Auto-chequeo al arrancar: AVISA en el log si algún comportamiento esperado se ha roto.
    try:
        from .selfcheck import alert_if_red

        alert_if_red()
    except Exception:
        pass

    # Calienta la COMPRENSIÓN de la bandeja en segundo plano: así el telar tiene el resultado bueno
    # listo desde el principio y NUNCA muestra el calendario crudo (el dato sin verificar).
    try:
        from .comprension import calentar_al_arrancar

        calentar_al_arrancar()
    except Exception:
        pass

    # Calienta la TELA en 2º plano: el telar se sirve cacheado al instante (sin esperar a Google en
    # cada request) y se refresca por detrás. Mata la pantalla en blanco al abrir (auditoría P0-3).
    try:
        from .telar_cache import warm as _warm_telar

        _warm_telar()
    except Exception:
        pass

    # Fábrica de Skills (Skill X): carga las tools que un humano APROBÓ (gate sagrado). Opt-in,
    # off por defecto; cada tool se re-verifica con el gate de seguridad antes de registrarse.
    if settings.fabrica_autocargar_generadas:
        try:
            from .fabrica.materializar import cargar_tools_aprobadas

            cargadas = cargar_tools_aprobadas()
            if cargadas:
                logging.getLogger(__name__).info(
                    "Fábrica: %d tool(s) aprobada(s) cargada(s): %s", len(cargadas), cargadas
                )
        except Exception:
            pass

    daemon = None
    if settings.routines_daemon_enabled:
        from .routine_executors import build_default_scheduler
        from .scheduler import SchedulerDaemon

        daemon = SchedulerDaemon(
            build_default_scheduler(), settings.routines_daemon_interval_seconds
        )
        daemon.start()
    try:
        yield
    finally:
        if daemon is not None:
            daemon.stop()


app = FastAPI(title="Loombit Operator", version="0.1.0", lifespan=lifespan)

# Rutas API
app.include_router(health.router)
app.include_router(skill_blanca_oauth.router)
app.include_router(skill_blanca_actions.router)
app.include_router(agent.router)
app.include_router(computer.router)
app.include_router(pilot.router)
app.include_router(docs.router)
app.include_router(routines.router)
app.include_router(fiscal.router)
app.include_router(conciliacion.router)
app.include_router(cuentas.router)
app.include_router(galaxia.router)
app.include_router(home.router)
app.include_router(credentials.router)
app.include_router(mcp.router)
app.include_router(telar.router)
app.include_router(fabrica.router)
app.include_router(rag.router)
app.include_router(entregable.router)

# UI estatico y home
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(ui.router)
