"""
system.py — ajustes de proceso para que el Pilot vea y pulse coordenadas reales.

El más crítico es la **DPI-awareness**: en Windows con escalado de pantalla
(125 %, 150 %…) un proceso no consciente del DPI recibe coordenadas y capturas
"virtualizadas", de modo que el clic cae en un sitio distinto del que el agente
ve en la captura. Activar per-monitor v2 alinea captura y clic a píxeles reales.

Idempotente y sin efecto en plataformas que no sean Windows.
"""

from __future__ import annotations

import logging
import sys

logger = logging.getLogger(__name__)

_DPI_DONE = False


def enable_dpi_awareness() -> dict[str, object]:
    """
    Marca el proceso como DPI-aware (per-monitor v2 si está disponible).

    Devuelve {enabled: bool, mode: str}. Solo actúa una vez por proceso.
    """
    global _DPI_DONE
    if _DPI_DONE:
        return {"enabled": True, "mode": "already-set"}
    if not sys.platform.startswith("win"):
        _DPI_DONE = True
        return {"enabled": False, "mode": "non-windows"}

    import ctypes

    # 1) Per-Monitor v2 (Windows 10 1703+): el modo preferido.
    try:
        # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
        if ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            _DPI_DONE = True
            return {"enabled": True, "mode": "per-monitor-v2"}
    except Exception as exc:
        logger.debug("SetProcessDpiAwarenessContext falló: %s", exc)

    # 2) Per-Monitor (Windows 8.1+): shcore.SetProcessDpiAwareness(2).
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        _DPI_DONE = True
        return {"enabled": True, "mode": "per-monitor"}
    except Exception as exc:
        logger.debug("SetProcessDpiAwareness falló: %s", exc)

    # 3) System-DPI-aware (legado): user32.SetProcessDPIAware().
    try:
        ctypes.windll.user32.SetProcessDPIAware()
        _DPI_DONE = True
        return {"enabled": True, "mode": "system"}
    except Exception as exc:
        logger.debug("SetProcessDPIAware falló: %s", exc)

    return {"enabled": False, "mode": "unavailable"}
