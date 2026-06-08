"""
fuentes.py — el ABANICO: registro expandible de fuentes de oportunidad de la Fábrica.

Cada fuente es un detector `(**ctx) -> list[Necesidad]`. El abanico cubre lo de DENTRO (proceso,
cognición, usuario) y lo de FUERA (la Red: competencia/mercado/noticias/tech/GitHub/BOE), y puede
CRECER: la fuente META propone añadir fuentes/escenarios nuevos. Registrar una fuente nueva es una
línea — por eso "que ella mejore su abanico" es construible.

`detectar()` lanza las fuentes activas, deja a META para el final (necesita ver lo que sacaron las
demás), y devuelve las oportunidades ordenadas por prioridad.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .modelos import Fuente, Necesidad
from .necesidad import detectar_necesidades
from .red import buscar_oportunidades_red

Detector = Callable[..., list[Necesidad]]


class FuenteRegistry:
    def __init__(self) -> None:
        self._fuentes: dict[Fuente, Detector] = {}

    def registrar(self, fuente: Fuente, detector: Detector) -> None:
        self._fuentes[fuente] = detector

    def fuentes(self) -> list[Fuente]:
        return list(self._fuentes)

    def detectar(self, fuentes: list[Fuente] | None = None, **ctx: Any) -> list[Necesidad]:
        """Lanza las fuentes activas (META al final, con los resultados de las demás)."""
        activas = fuentes if fuentes is not None else list(self._fuentes)
        resultados: dict[Fuente, list[Necesidad]] = {}
        for f in activas:
            if f == Fuente.META or f not in self._fuentes:
                continue
            try:
                resultados[f] = self._fuentes[f](**ctx) or []
            except Exception:  # noqa: BLE001 — una fuente caída no tumba el abanico
                resultados[f] = []

        out: list[Necesidad] = [n for lst in resultados.values() for n in lst]
        if Fuente.META in activas and Fuente.META in self._fuentes:
            try:
                out += self._fuentes[Fuente.META](resultados_por_fuente=resultados, **ctx) or []
            except Exception:  # noqa: BLE001
                pass
        out.sort(key=lambda n: n.prioridad, reverse=True)
        return out


# ── Detectores por defecto (cada uno toma del ctx lo que necesita) ──────────────


def _det_proceso(**ctx: Any) -> list[Necesidad]:
    return detectar_necesidades(memoria=ctx.get("memoria"), store=ctx.get("store_runs"))


def _det_red(**ctx: Any) -> list[Necesidad]:
    return buscar_oportunidades_red(http_get=ctx.get("http_get"))


def _det_cognicion(**_ctx: Any) -> list[Necesidad]:
    from .interno import marcar

    return marcar()


def _det_meta(**ctx: Any) -> list[Necesidad]:
    from .meta import detectar_meta

    return detectar_meta(
        resultados_por_fuente=ctx.get("resultados_por_fuente"),
        store_prop=ctx.get("store_prop"),
    )


def registro_por_defecto() -> FuenteRegistry:
    """El abanico de serie: proceso (dentro) + red (fuera) + meta (auto-expansión)."""
    reg = FuenteRegistry()
    reg.registrar(Fuente.PROCESO, _det_proceso)
    reg.registrar(Fuente.COGNICION, _det_cognicion)
    reg.registrar(Fuente.RED, _det_red)
    reg.registrar(Fuente.META, _det_meta)
    return reg
