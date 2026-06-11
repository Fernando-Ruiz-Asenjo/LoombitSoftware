"""
autonomy.py — LD-3 de «Loombit Decide»: autonomía GRADUADA (y capada con honestidad).

El operador pasa de «responde cuando le hablas» a **trabajar en background y encolar decisiones**. Pero
la autonomía se **gradúa y se mide, no se promete** (§14B: el 14B local limita la autonomía real). Los
niveles:

  observa          → ve el trabajo, NO lo sube (cuenta, no molesta)
  propone          → encola la decisión en la cola; el humano decide (DEFAULT)
  actua_con_gate   → encola; el acto, cuando el humano aprueba, pasa por el gate (= LD-2)
  actua_solo       → actuaría sin humano en lo reversible — **NO IMPLEMENTADO** (declarado, no fingido)

Garantía: este generador **solo encola decisiones**; NUNCA dispara un efecto externo ni auto-resuelve
una decisión. `actua_solo` se trata como `propone` y se reporta `auto_actuado=0`. El acto consecuente
sigue exigiendo al humano (la cola) y al gate (el envío). El LLM no está en el camino de control.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Any

from .decisions import DecisionStore
from .decisions_cobros import decisiones_de_cobros


class AutonomyLevel(StrEnum):
    OBSERVA = "observa"
    PROPONE = "propone"
    ACTUA_CON_GATE = "actua_con_gate"
    ACTUA_SOLO = "actua_solo"


# Niveles que SÍ suben la decisión a la cola (de `propone` hacia arriba).
_ENCOLAN = {AutonomyLevel.PROPONE, AutonomyLevel.ACTUA_CON_GATE, AutonomyLevel.ACTUA_SOLO}


def nivel_encola(level: AutonomyLevel) -> bool:
    """¿Este nivel sube la decisión a la cola? (`observa` no molesta; el resto sí.)"""
    return level in _ENCOLAN


def parse_level(value: str | AutonomyLevel | None) -> AutonomyLevel:
    """Tolerante: un valor desconocido cae al nivel seguro por defecto (`propone`)."""
    if isinstance(value, AutonomyLevel):
        return value
    try:
        return AutonomyLevel(str(value))
    except ValueError:
        return AutonomyLevel.PROPONE


def generar_decisiones_cobro(
    decision_store: DecisionStore,
    vencidas: list[Any],
    *,
    today: str | date | None = None,
    level: AutonomyLevel = AutonomyLevel.PROPONE,
) -> dict[str, Any]:
    """Compone las decisiones de cobro de las cuentas vencidas y, según el nivel, las encola
    (idempotente por `cuenta_id`). NUNCA actúa sola: `auto_actuado` es siempre 0 (§14B — `actua_solo`
    no está construido; se declara, no se finge)."""
    decisiones = decisiones_de_cobros(vencidas, today)
    encoladas: list[str] = []
    if nivel_encola(level):
        existentes = {
            d.source.get("cuenta_id") for d in decision_store.list() if d.source.get("cuenta_id")
        }
        for d in decisiones:
            if d.source.get("cuenta_id") in existentes:
                continue  # ya hay una decisión para esa cuenta → no duplicar
            decision_store.add(d)
            encoladas.append(d.id)
    return {
        "observadas": len(decisiones),
        "encoladas": len(encoladas),
        "ids": encoladas,
        "nivel": level.value,
        "auto_actuado": 0,  # invariante: el generador no dispara efectos ni auto-resuelve
    }
