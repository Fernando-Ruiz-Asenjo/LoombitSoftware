"""
meta.py — fuente META: la Fábrica AMPLÍA su propio abanico de escenarios de mejora.

No detecta un hueco del producto, sino un hueco de la PROPIA Fábrica: una fuente que está seca,
un patrón de fallos que pide abrir un escenario nuevo, o un canal de radar que falta. Es la
auto-mejora del motor de auto-mejora (lo que pidió Fernando: "que ella mejore su abanico").
Como todo, son propuestas con gate humano — la Fábrica no se reconfigura sola.
"""

from __future__ import annotations

from typing import Any

from .modelos import EstadoPropuesta, Fuente, Necesidad, TipoNecesidad


def detectar_meta(
    resultados_por_fuente: dict[Fuente, list[Necesidad]] | None = None,
    store_prop: Any = None,
    **_: Any,
) -> list[Necesidad]:
    """Propone ampliaciones del abanico a partir de cómo le está yendo a la propia Fábrica."""
    propuestas: list[Necesidad] = []
    resultados = resultados_por_fuente or {}

    # 1) Una fuente que no aporta señal → revisar/ampliar su cobertura.
    for fuente, hallazgos in resultados.items():
        if not hallazgos:
            propuestas.append(
                Necesidad(
                    titulo=f"Ampliar la fuente '{fuente.value}': no produjo oportunidades",
                    tipo=TipoNecesidad.MEJORA,
                    fuente=Fuente.META,
                    descripcion="Revisar sus consultas/canales/cobertura para que aporte señal útil.",
                    prioridad=2,
                    procedencia=[f"meta:cobertura:{fuente.value}"],
                )
            )

    # 2) Mucho fallo de autoría de tools → abrir el escenario de auto-evolución de cognición.
    if store_prop is not None:
        try:
            fallidas = len(store_prop.list(EstadoPropuesta.FALLIDA))
        except Exception:  # noqa: BLE001
            fallidas = 0
        if fallidas >= 3:
            propuestas.append(
                Necesidad(
                    titulo="Abrir escenario: MEJORAR skills/prompts existentes (no solo crear tools)",
                    tipo=TipoNecesidad.MEJORA,
                    fuente=Fuente.META,
                    descripcion=(
                        f"{fallidas} intentos de tool no pasaron el arnés: la autoría de tools puras "
                        "topa. Ampliar el abanico hacia la auto-evolución de la cognición (GEPA/SICA)."
                    ),
                    prioridad=3,
                    procedencia=["meta:linaje"],
                )
            )

    # 3) Propuesta permanente de ensanchar el radar (competencia directa).
    propuestas.append(
        Necesidad(
            titulo="Nuevo canal de radar: changelogs/ProductHunt de competidores directos",
            tipo=TipoNecesidad.MEJORA,
            fuente=Fuente.META,
            descripcion="Vigilar lanzamientos de competidores para no perder vías de producto/monetización.",
            prioridad=1,
            procedencia=["meta:abanico"],
        )
    )
    return propuestas
