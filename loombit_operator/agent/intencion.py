"""
Detección DETERMINISTA de intención CONSECUENTE — para FORZAR la herramienta.

El 14B a veces responde a ojo en cobros/303/facturas (cálculos), inventando cifras (p.ej. un
interés de demora del 4,5 % en vez del legal del BOE) en vez de llamar a la tool determinista.
Aquí detectamos esas intenciones por palabra clave: cuando lo son, el bucle fuerza `tool_choice`
para que el modelo NO pueda calcular a mano. La tool correcta la elige él entre las que el router
ya filtró (cobro→plan_cobro, 303→calcular_303, factura→registrar_factura).

Puro y testeable. Ver docs/ALGORITMO_CEREBRO.md.
"""

from __future__ import annotations

import re

# Intenciones donde el resultado son CIFRAS que deben salir de código, no del LLM.
_COBRO = re.compile(r"\b(cobro|cobrar|reclam\w+|moros\w+|impag\w+|deuda|deudas|vencid\w+|demora)\b")
_F303 = re.compile(r"\b(303|iva|trimestral|repercutid\w+|soportad\w+|devengad\w+|liquidaci[oó]n)\b")
_FACTURA = re.compile(r"\b(factura|facturas|fact[uú]rame|emit\w+|registrar|reg[ií]strame)\b")
# Búsqueda en el correo: el 14B a veces DICE que buscó sin buscar (0 tools) e inventa el resultado.
# Forzamos la tool para que busque de verdad.
_BUSCAR_CORREO = re.compile(
    r"\b(busca\w*|b[uú]scame|encuentra|revisa|mira)\b[^\n]{0,25}\b"
    r"(correo|correos|email|e-mail|mail|bandeja|mensaje\w*|inbox)\b"
)


def fuerza_tool(task: str) -> bool:
    """True si la petición EXIGE una herramienta: cobro/303/factura (no fabricar cifras a ojo) o
    buscar en el correo (no decir que buscó sin buscar). El bucle forzará tool_choice."""
    t = (task or "").lower()
    return bool(
        _COBRO.search(t) or _F303.search(t) or _FACTURA.search(t) or _BUSCAR_CORREO.search(t)
    )
