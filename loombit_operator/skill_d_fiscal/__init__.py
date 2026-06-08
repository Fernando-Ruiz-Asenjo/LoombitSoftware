"""
Skill D Fiscal — dominio fiscal español. Depende de Skill W (Expediente) y NO lo contamina.

Regla de oro: el número NUNCA lo pone un LLM; aquí se calcula con Decimal y se cuadra. El
303 es el primer modelo; el patrón sirve para 130/111/115/347/390/200… Ver
`docs/PLATAFORMA_FISCAL_ANALISIS.md` y `docs/ARQUITECTURA_SKILLS.md`.
"""

from .intake import (
    inferir_tipo_iva,
    linea_desde_factura,
    liquidar_303_periodo,
    recopilar_lineas,
    registrar_factura,
)
from .modelo_303 import (
    LineaIVA,
    Resultado303,
    borrador_303_texto,
    calcular_303,
    procesar_303,
)

__all__ = [
    "LineaIVA",
    "Resultado303",
    "borrador_303_texto",
    "calcular_303",
    "inferir_tipo_iva",
    "linea_desde_factura",
    "liquidar_303_periodo",
    "procesar_303",
    "recopilar_lineas",
    "registrar_factura",
]
