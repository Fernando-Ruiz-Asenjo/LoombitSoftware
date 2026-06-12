"""
cobros_flujo.py — ORQUESTADOR del lazo de cobros: pendientes → (al aprobar) envío. Sin saltarse el gate.

Une las piezas ya construidas: `seguimiento_cobros` (vencidas → decisión) + `envio_cobro` (envío con gate
de efecto). `pendientes()` solo LISTA (no envía nada); `aprobar_y_enviar()` es la ACCIÓN del humano que
aprueba una decisión → dispara su envío, que SIGUE validando dentro (aprobación + cifras por código).

El LLM no interviene: las cifras y el envío los rige el código (Ley Fundacional / §14B-1 / gate de efecto).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from ..cuentas_cobrar import CuentasCobrarStore
from .envio_cobro import enviar_recordatorio
from .seguimiento_cobros import decisiones_pendientes


def pendientes(store_cc: CuentasCobrarStore, today: str | date | None = None) -> list[Any]:
    """Las decisiones de cobro pendientes de aprobar (vencidas → decisión). NO envía nada: solo lista."""
    return decisiones_pendientes(store_cc, today)


def aprobar_y_enviar(decision: Any, **kw: Any) -> dict[str, Any]:
    """El humano APRUEBA esta decisión → se dispara su envío. Llamar a esto ES la aprobación; el envío
    sigue validando dentro (gate de efecto + cifras por código). Devuelve el recibo."""
    return enviar_recordatorio(decision, aprobada=True, **kw)
