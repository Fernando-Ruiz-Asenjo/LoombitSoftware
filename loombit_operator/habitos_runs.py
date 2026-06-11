"""
habitos_runs.py — adaptador entre las decisiones del agente y el motor de hábitos.

Cuando el usuario APRUEBA o RECHAZA una sugerencia PROACTIVA de Loombit (un run creado por el
daemon, no algo que el usuario pidió), aquí se traduce esa decisión a una observación de
`habitos.py`. Así el telar aprende a quién sueles responder y qué sueles ignorar, y anticipa.

Sólo se aprende de runs `proactive=True`: lo que el usuario pide explícitamente NO es una
"sugerencia" que aceptar/rechazar. El efecto externo sigue requiriendo aprobación siempre; esto
sólo afina la ANTICIPACIÓN. Núcleo blanco (no asume dominio).
"""

from __future__ import annotations

import re
from typing import Any

from .habitos import get_habits

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_EVENTO = ("calendar", "evento", "reunión", "reunion", "cita", "invitación", "invitacion")


def tipo_sujeto_de_run(run: Any) -> tuple[str, str] | None:
    """(tipo, sujeto) de un run proactivo para aprender el hábito. El sujeto = el destinatario
    (email), extraído del `proposed_action`/`reason` de la aprobación o, si falta, del `task`.
    `tipo` = 'evento' si la acción es de calendario, si no 'respuesta'. None si no hay destinatario.
    """
    pa = getattr(run, "pending_approval", None) or {}
    texto = " ".join(
        [
            str(pa.get("proposed_action", "")),
            str(pa.get("reason", "")),
            str(getattr(run, "task", "") or ""),
        ]
    )
    m = _EMAIL.search(texto)
    if not m:
        return None
    sujeto = m.group(0).lower()
    tipo = "evento" if any(k in texto.lower() for k in _EVENTO) else "respuesta"
    return tipo, sujeto


def registrar_decision_run(run: Any, decision: str) -> bool:
    """Aprende el hábito de la decisión del usuario sobre una sugerencia PROACTIVA. Devuelve True
    si registró. No-op silencioso (nunca rompe el flujo de aprobación) si el run no es proactivo,
    no tiene destinatario, o falla la escritura."""
    if not getattr(run, "proactive", False):
        return False
    ts = tipo_sujeto_de_run(run)
    if not ts:
        return False
    try:
        get_habits().registrar(ts[0], ts[1], decision, meta={"run_id": getattr(run, "id", "")})
        return True
    except Exception:
        return False
