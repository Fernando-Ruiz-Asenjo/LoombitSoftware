"""
routers/galaxia.py — la Galaxia: el negocio como sistema estelar (`docs/GALAXIA_LOOMBIT.md`).

GET /galaxia → `{ sol, nodos[], aristas[], meta }` agregando contactos (Enviados) + cuentas a
cobrar + aristas contacto↔cuenta. Caché TTL corta porque la UI lo refresca en bucle y los
contactos tocan Gmail; `?force=1` la salta.
"""

from __future__ import annotations

import time

from fastapi import APIRouter

from ..galaxia import build_galaxia

router = APIRouter(tags=["galaxia"])

_TTL_S = 20.0
_cache: dict[str, object] = {"ts": 0.0, "data": None}


@router.get("/galaxia")
def galaxia(force: bool = False) -> dict:
    ahora = time.monotonic()
    if not force and _cache["data"] is not None and (ahora - float(_cache["ts"])) < _TTL_S:
        return _cache["data"]  # type: ignore[return-value]
    data = build_galaxia()
    _cache["ts"] = ahora
    _cache["data"] = data
    return data
