"""
telar_cache.py — sirve la tela del día AL INSTANTE desde caché y refresca Google en 2º plano.

Problema (auditoría UX, P0-3): `telar.tejer_dia()` hace llamadas SÍNCRONAS a Google en CADA
request (eventos + correos + bandeja, hasta ~12 s cada una) → 5-30 s de pantalla en blanco al
abrir Loombit. Eso rompe la ley nº1 («te recibe con lo ya hecho, no con un cursor vacío»).

Solución: caché en memoria + disco. Se devuelve el último telar BUENO sin esperar a Google y un
hilo de fondo lo mantiene fresco. Tras reiniciar el servidor, se sirve el último telar del disco al
instante. NUNCA inventa: si no hay caché todavía, computa una vez (síncrono), lo guarda y lo sirve.
El payload lleva `meta.cache` (edad + si se está refrescando) para no mentir sobre su frescura.

Todo inyectable (`tejer=`) → testeable sin red ni LLM.
"""

from __future__ import annotations

import copy
import json
import threading
import time
from pathlib import Path
from typing import Any, Callable

# Si el caché es más viejo que esto, se refresca en 2º plano (sin bloquear el request).
_REFRESH_AFTER = 60.0

_lock = threading.Lock()
_refreshing = False
_mem: dict[str, Any] | None = None  # {"ts": float, "data": dict}


def _cache_path() -> Path:
    from .config import get_settings

    base = Path(get_settings().agent_run_store_path).parent
    return base / "telar_cache.json"


def _load_disk() -> dict[str, Any] | None:
    try:
        return json.loads(_cache_path().read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_disk(entry: dict[str, Any]) -> None:
    try:
        p = _cache_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(p)
    except Exception:
        pass  # el caché es best-effort; nunca debe tumbar el telar


def _default_tejer() -> dict:
    from .telar import tejer_dia

    return tejer_dia()


def _compute(tejer: Callable[[], dict]) -> dict[str, Any]:
    return {"ts": time.time(), "data": tejer()}


def _refresh_async(tejer: Callable[[], dict]) -> None:
    """Refresca el caché en un hilo de fondo (uno a la vez). No bloquea al usuario."""
    global _refreshing
    with _lock:
        if _refreshing:
            return
        _refreshing = True

    def _run() -> None:
        global _mem, _refreshing
        try:
            entry = _compute(tejer)
            _mem = entry
            _save_disk(entry)
        except Exception:
            pass
        finally:
            with _lock:
                _refreshing = False

    threading.Thread(target=_run, daemon=True, name="telar-refresh").start()


def _con_meta_cache(data: dict, edad: float) -> dict:
    out = copy.deepcopy(data)
    out.setdefault("meta", {})["cache"] = {"edad_s": int(edad), "refrescando": _refreshing}
    return out


def get_telar(tejer: Callable[[], dict] | None = None) -> dict:
    """La tela del día AL INSTANTE: caché (memoria→disco) + refresco en 2º plano si está vieja.
    Solo computa síncrono la PRIMERA vez (cuando no hay ningún caché)."""
    global _mem
    tejer = tejer or _default_tejer
    entry = _mem or _load_disk()
    if entry and isinstance(entry.get("data"), dict):
        _mem = entry
        edad = time.time() - float(entry.get("ts", 0))
        if edad > _REFRESH_AFTER:
            _refresh_async(tejer)
        return _con_meta_cache(entry["data"], edad)
    # Nunca computado: paga el coste UNA vez, guarda y sirve.
    entry = _compute(tejer)
    _mem = entry
    _save_disk(entry)
    return _con_meta_cache(entry["data"], 0)


def warm(tejer: Callable[[], dict] | None = None) -> None:
    """Calienta el caché en 2º plano al arrancar (para que el primer request sea instantáneo)."""
    _refresh_async(tejer or _default_tejer)


def _reset_para_tests() -> None:  # pragma: no cover - utilidad de test
    global _mem, _refreshing
    _mem = None
    _refreshing = False
