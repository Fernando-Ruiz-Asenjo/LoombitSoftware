"""
selfcheck.py — auto-verificación que se aplica sola y AVISA si algo dejó de funcionar.

Corre el eval-set determinista (`evals/`) desde el propio código del producto, no a mano. Lo usan:
- el ARRANQUE del servidor (alerta fuerte en el log si hay rojo),
- el endpoint `/health/selfcheck` (lo consulta la UI o un monitor),
- CI (`tests/test_evals.py`).

Honestidad (DoD): NO prueba "es perfecto". Prueba que los comportamientos conocidos de la
taxonomía F1-F8 siguen verdes — que no hemos REGRESADO. Lo que aún no tiene eval se reporta aparte.
Ver `docs/METODO_INGENIERIA_IA_LOOMBIT.md`.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def run_selfcheck() -> dict[str, Any]:
    """Ejecuta los evals deterministas y devuelve un resultado estructurado (ok/verdes/fallos)."""
    try:
        from evals.cases import CASES
    except Exception as exc:  # el eval-set no es importable → degradado, pero no rompe el servidor
        return {"ok": False, "error": f"eval-set no importable: {exc!r}", "total": 0}

    casos: list[dict[str, Any]] = []
    fallos: list[str] = []
    for ev in CASES:
        if ev.check is None or ev.needs_llm:
            continue  # huecos conocidos y los de juez-LLM no entran en el auto-chequeo rápido
        try:
            ok, detalle = ev.check()
        except Exception as exc:
            ok, detalle = False, repr(exc)
        casos.append({"id": ev.id, "taxon": ev.taxon, "ok": ok, "detalle": detalle})
        if not ok:
            fallos.append(ev.id)

    pendientes = [ev.id for ev in CASES if ev.check is None]
    return {
        "ok": not fallos,
        "verdes": len(casos) - len(fallos),
        "total": len(casos),
        "fallos": fallos,
        "pendientes_sin_eval": pendientes,
        "casos": casos,
    }


def alert_if_red() -> dict[str, Any]:
    """Para el arranque: corre el auto-chequeo y deja una ALERTA en el log si algo falló."""
    res = run_selfcheck()
    if res.get("ok"):
        logger.info(
            "Auto-chequeo OK: %d/%d evals verdes.", res.get("verdes", 0), res.get("total", 0)
        )
    else:
        logger.warning(
            "⚠️  AUTO-CHEQUEO EN ROJO: fallan %s. El comportamiento esperado se ha roto — revisar.",
            ", ".join(res.get("fallos", [])) or res.get("error", "?"),
        )
    return res
