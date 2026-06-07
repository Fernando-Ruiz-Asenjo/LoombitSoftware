"""Punto de entrada FastAPI. Solo crea la app y monta routers (anti-monolito)."""
from __future__ import annotations

import os
import sys
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
# ─────────────────────────────────────────────────────────────────────────────

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .routers import agent, computer, health, pilot, skill_blanca_actions, skill_blanca_oauth, ui

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Loombit Operator", version="0.1.0")

# Rutas API
app.include_router(health.router)
app.include_router(skill_blanca_oauth.router)
app.include_router(skill_blanca_actions.router)
app.include_router(agent.router)
app.include_router(computer.router)
app.include_router(pilot.router)

# UI estatico y home
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(ui.router)
