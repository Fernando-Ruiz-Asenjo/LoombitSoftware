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
