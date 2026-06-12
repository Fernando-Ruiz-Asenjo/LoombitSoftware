"""
seguimiento_cobros.py — el LAZO de cobros: cuentas a cobrar → vencidas → decisión de cobro lista.

Promesa firmada (`docs/PROMESAS.jsonl` · seguimiento-cobros): tras meter las facturas, detecta las
VENCIDAS y compone, por cada una, su DECISIÓN de cobro lista para aprobar — con el importe legal
(saldo + 40 € art. 8 + interés de demora) calculado por CÓDIGO (`cobros.py`), y SIN enviar nada solo
(gate humano). Las no vencidas no generan decisión.

Conecta lo que ya existe, sin reinventar: `cuentas_cobrar.vencidas()` + `decisions_cobros`. El envío real
por email (con recibo) es el paso siguiente (LD-1 / gate de efecto), FUERA de esta promesa.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from ..cuentas_cobrar import CuentasCobrarStore
from ..decisions_cobros import decisiones_de_cobros


def decisiones_pendientes(
    store_cc: CuentasCobrarStore, today: str | date | None = None
) -> list[Any]:
    """De las cuentas a cobrar, detecta las VENCIDAS y compone su decisión de cobro (lista para aprobar).
    Las no vencidas se omiten. NO envía nada: cada decisión es una PROPUESTA con su gate de aprobación —
    el importe legal lo pone `cobros.py` (determinista), el LLM no interviene."""
    return decisiones_de_cobros(store_cc.vencidas(today), today)
