"""
ALG-0.1 · asegurar_contexto — que el prompt + tools quepan en el contexto del modelo.

Si el system prompt + las tools + el historial superan el contexto cargado del modelo, LM Studio
devuelve `400` ("n_keep >= n_ctx") y el run muere mudo. Esto lo evita por construcción: estima el
coste y, si no cabe, RECORTA — primero el historial intermedio (conserva el system y el último turno
del usuario), y solo como último recurso poda tools. Determinista y testeable (100% en el gate).

Blanco/reutilizable: no asume dominio. Ver docs/REPARACION_CANONICA.md (ALG-0.1).
"""

from __future__ import annotations

import json
from typing import Any


def estimar_tokens(obj: Any) -> int:
    """Estimación CONSERVADORA (sobreestima) de tokens: ~3 chars/token sobre el JSON serializado.

    No necesitamos exactitud (no hay tokenizer del modelo a mano); necesitamos un techo seguro
    para no pasarnos del contexto. Sobreestimar es lo correcto aquí."""
    if obj is None:
        return 0
    txt = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False)
    return (len(txt) + 2) // 3


def ajustar_a_contexto(
    messages: list[dict],
    tools: list[dict],
    *,
    n_ctx: int,
    max_tokens: int,
    margen: int = 256,
    min_tools: int = 4,
) -> tuple[list[dict], list[dict], bool]:
    """Devuelve (messages, tools, recortado) que caben en el presupuesto de contexto.

    - Nunca toca el system (`messages[0]`) ni deja menos de 1 turno de conversación.
    - Conserva al menos `min_tools` herramientas.
    - `recortado` = True si hubo que podar algo (para poder avisar/loguear).
    """
    presupuesto = max(n_ctx - max_tokens - margen, 512)

    def coste(m: list[dict], t: list[dict]) -> int:
        return estimar_tokens(m) + estimar_tokens(t)

    if coste(messages, tools) <= presupuesto:
        return messages, tools, False

    recortado = False
    msgs = list(messages)

    # 1) Podar historial intermedio: conserva system + el ÚLTIMO turno; quita los más antiguos.
    if len(msgs) > 2:
        system = msgs[0]
        cola = msgs[1:]
        while len(cola) > 1 and coste([system, *cola], tools) > presupuesto:
            cola.pop(0)
            recortado = True
        msgs = [system, *cola]

    # 2) Último recurso: podar tools (mantener al menos min_tools).
    t = list(tools)
    while len(t) > min_tools and coste(msgs, t) > presupuesto:
        t.pop()
        recortado = True

    return msgs, t, recortado
