"""Calculo fiscal determinista de IVA (modelo 303) - modulo de DEMO.

Sirve para demostrar el sistema de verificacion: es codigo de dominio fiscal
simple cuyo resultado correcto se conoce por LEY (Ley 37/1992 del IVA, tipo
general 21 %), no por lo que diga el propio codigo.
"""

from __future__ import annotations

TIPO_GENERAL = 0.21  # IVA tipo general en Espana (Ley 37/1992, art. 90)


def cuota_iva(base_imponible: float, tipo: float = TIPO_GENERAL) -> float:
    """Cuota de IVA de una base imponible. base * tipo."""
    return round(base_imponible * tipo, 2)


def iva_a_ingresar(
    base_repercutida: float, base_soportada: float, tipo: float = TIPO_GENERAL
) -> float:
    """Modelo 303: IVA repercutido (cobrado) menos IVA soportado (pagado)."""
    return round(cuota_iva(base_repercutida, tipo) - cuota_iva(base_soportada, tipo), 2)
