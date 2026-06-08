"""
galaxia_cache.py — pre-carga de la Galaxia (stale-while-revalidate).

Antes la Galaxia se construía al abrirla (`/galaxia?force=1`), tocando Gmail → la
primera apertura iba lenta. Aquí la servimos SIEMPRE al instante desde el último
snapshot y, si está rancio, disparamos un refresco en segundo plano (sin bloquear ni
montar un daemon que machaque Gmail cuando nadie mira). El frontend, además, precarga
al cargar la página, así al pulsar 🌌 ya está fresca con lo de hoy.

Sin estado global de dominio: solo cachea lo que produce `build_galaxia()`.
"""

from __future__ import annotations

import threading
import time
from typing import Any

from .galaxia import build_galaxia

_LOCK = threading.Lock()
_snap: dict[str, Any] | None = None
_ts: float = 0.0
_refreshing = False


def _store(data: dict[str, Any]) -> None:
    global _snap, _ts
    with _LOCK:
        _snap = data
        _ts = time.monotonic()


def _refresh_bg() -> None:
    global _refreshing
    try:
        data = build_galaxia()
        _store(data)
    except Exception:
        pass  # el panel es complementario; si falla, seguimos con el snapshot viejo
    finally:
        with _LOCK:
            _refreshing = False


def _with_meta(data: dict[str, Any]) -> dict[str, Any]:
    """Añade la edad del snapshot para que la UI muestre la frescura."""
    out = dict(data)
    meta = dict(out.get("meta") or {})
    with _LOCK:
        meta["edad_seg"] = round(time.monotonic() - _ts, 1) if _snap is not None else 0.0
    out["meta"] = meta
    return out


def get(max_age: float = 20.0, force: bool = False) -> dict[str, Any]:
    """Devuelve el snapshot de la Galaxia.

    - Frío (no hay snapshot) o `force`: construye sincrónico (única espera posible).
    - Caliente y fresco: lo devuelve al instante.
    - Caliente pero rancio (> max_age): lo devuelve al instante Y revalida en background.
    """
    global _refreshing
    with _LOCK:
        snap = _snap
        age = (time.monotonic() - _ts) if _snap is not None else None

    if snap is None or force:
        data = build_galaxia()
        _store(data)
        return _with_meta(data)

    if age is not None and age > max_age:
        with _LOCK:
            if not _refreshing:
                _refreshing = True
                threading.Thread(target=_refresh_bg, daemon=True).start()
    return _with_meta(snap)


def prewarm() -> None:
    """Calienta el snapshot en segundo plano (no bloquea). Para llamar al arrancar."""
    global _refreshing
    with _LOCK:
        if _refreshing or _snap is not None:
            return
        _refreshing = True
    threading.Thread(target=_refresh_bg, daemon=True).start()
