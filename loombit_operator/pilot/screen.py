"""
screen.py — captura de pantalla local.

Usa PIL.ImageGrab (Windows nativo). No sube nada a la nube.
La imagen puede guardarse en disco y/o devolverse como base64.
"""

from __future__ import annotations

import base64
import io
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def take_screenshot(
    save_dir: Path | None = None,
    include_base64: bool = True,
    region: tuple[int, int, int, int] | None = None,
) -> dict[str, Any]:
    """
    Captura la pantalla completa o una región.

    Args:
        save_dir: Si se indica, guarda la imagen en este directorio.
        include_base64: Si True, incluye la imagen como base64 en el resultado.
        region: (x0, y0, x1, y1) para capturar sólo una región.

    Returns:
        dict con width, height, format, base64 (opcional), saved_path (opcional).
    """
    try:
        from PIL import ImageGrab  # type: ignore
    except ImportError:
        return {"error": "Pillow no instalado. Ejecuta: pip install pillow"}

    try:
        img = ImageGrab.grab(bbox=region, all_screens=True)
    except TypeError:
        # Pillow antiguo no soporta all_screens
        img = ImageGrab.grab(bbox=region)

    result: dict[str, Any] = {
        "width": img.width,
        "height": img.height,
        "format": "PNG",
    }

    if include_base64:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        result["base64"] = base64.b64encode(buf.getvalue()).decode()

    if save_dir:
        try:
            save_dir = Path(save_dir)
            save_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
            path = save_dir / f"screenshot_{ts}.png"
            img.save(path)
            result["saved_path"] = str(path)
            logger.info("Screenshot guardado: %s", path)
        except Exception as exc:
            result["save_error"] = str(exc)

    return result


def screen_changed(threshold: float = 0.02, interval: float = 0.5) -> dict[str, Any]:
    """
    Captura dos frames separados por `interval` segundos y reporta si una
    fracción de píxeles mayor que `threshold` (0..1) ha cambiado.

    Sirve para que el agente detecte si la pantalla está reaccionando a una
    acción (carga, animación, repintado) antes de continuar.

    Returns:
        dict con changed (bool), fraction (0..1), threshold, interval.
    """
    try:
        from PIL import ImageChops, ImageGrab  # type: ignore
    except ImportError:
        return {"error": "Pillow no instalado. Ejecuta: pip install pillow"}

    import time

    def _grab():
        try:
            return ImageGrab.grab(all_screens=True).convert("L")
        except TypeError:
            return ImageGrab.grab().convert("L")

    threshold = min(1.0, max(0.0, float(threshold)))
    before = _grab()
    time.sleep(max(0.0, float(interval)))
    after = _grab()

    if before.size != after.size:
        return {"changed": True, "fraction": 1.0, "reason": "la resolución cambió"}

    diff = ImageChops.difference(before, after)
    if diff.getbbox() is None:
        return {"changed": False, "fraction": 0.0, "threshold": threshold}

    # Cuenta píxeles que cambian de forma significativa (>16 niveles de gris).
    mask = diff.point(lambda p: 255 if p > 16 else 0)
    changed_pixels = mask.histogram()[255]
    total = before.width * before.height
    fraction = (changed_pixels / total) if total else 0.0

    return {
        "changed": fraction > threshold,
        "fraction": round(fraction, 5),
        "threshold": threshold,
        "interval": interval,
    }
