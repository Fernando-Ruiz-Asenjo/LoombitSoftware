"""
ui_audit.py — auditoría FUNCIONAL ligera de la UI (lo que la higiene de CÓDIGO no ve).

Origen (2026-06-09): Fernando cazó botones que "se pintaban" pero no HACÍAN nada (el ⚙️ Ajustes,
"Editar"). La Fábrica audita el código (bugs/lints/TODO) pero NO la función de la interfaz, así que
no los detectó. Esto cubre ese hueco: detección estática y barata de elementos interactivos sin
acción. Pensado para (a) un test de regresión y (b) que la higiene de la Fábrica lo consuma.

Heurística (conservadora, bajo falso positivo): un `<button>` sin `onclick`, sin `type=submit` y sin
`type=button` es casi seguro decorativo/muerto — fue exactamente la firma del ⚙️ y de "Editar". Los
botones cableados por JS deben declarar `type="button"` (buena práctica), así que no se marcan.
"""

from __future__ import annotations

import re

_BTN = re.compile(r"<button\b[^>]*>", re.IGNORECASE)
_TIPO_OK = re.compile(r"""type\s*=\s*['"](submit|button|reset)['"]""", re.IGNORECASE)


def botones_sin_funcion(html: str) -> list[str]:
    """Devuelve las etiquetas `<button …>` SIN forma alguna de acción (ni onclick, ni type=submit/
    button/reset). Casi siempre = botón muerto/decorativo."""
    muertos: list[str] = []
    for m in _BTN.finditer(html or ""):
        tag = m.group(0)
        low = tag.lower()
        if "onclick=" in low or _TIPO_OK.search(low):
            continue
        muertos.append(tag[:140])
    return muertos


def auditar_ui(html: str) -> dict[str, list[str]]:
    """Parte de auditoría funcional de un HTML de UI. Hoy: botones muertos. Ampliable (enlaces vacíos,
    handlers que apuntan a funciones inexistentes, etc.) — el gancho para la Fábrica."""
    return {"botones_sin_funcion": botones_sin_funcion(html)}
