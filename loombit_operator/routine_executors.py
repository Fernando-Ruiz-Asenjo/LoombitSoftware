"""
routine_executors.py — ejecutores concretos para las Routines + armado por defecto.

El motor (`scheduler.py`) es neutro y recibe un executor inyectado. Aquí vive el
executor real basado en el LLM instructor (14B) y el armado del scheduler por defecto
(store seedeado con el Brief diario). Separado para evitar import circular con el router.
"""

from __future__ import annotations

from datetime import datetime

from .llm import LLMClient
from .routines import Routine, RoutineStore, brief_diario_routine
from .scheduler import RoutineScheduler

_BRIEF_SYSTEM = (
    "Eres Loombit, operador administrativo local. Responde SIEMPRE en español, en un "
    "brief de máximo 5 líneas, en lenguaje natural, sin JSON ni markdown."
)


def brief_executor(routine: Routine, now: datetime) -> str:
    """Compone el output de una rutina con el LLM instructor (rol por defecto = 14B).

    Honesto: aún no hay conectores de lectura (Gmail/Calendar/banco), así que el
    contexto es mínimo y se declara como tal; el brief crecerá cuando esas fuentes existan.
    """
    contexto = (
        "Aún no hay fuentes conectadas (Gmail/Calendar/banco). "
        "Genera un brief honesto de demostración con la estructura pedida; no inventes datos."
    )
    messages = [
        {"role": "system", "content": _BRIEF_SYSTEM},
        {"role": "user", "content": f"{routine.objective}\n\nContexto disponible: {contexto}"},
    ]
    return LLMClient().chat(messages, max_tokens=300).content.strip()


def ensure_default_routines(store: RoutineStore) -> RoutineStore:
    """Siembra el Brief diario si el store está vacío."""
    if not store.list():
        store.add(brief_diario_routine())
    return store


def build_default_scheduler() -> RoutineScheduler:
    """Store seedeado + scheduler con el executor de brief. Usado por el router y el daemon."""
    store = ensure_default_routines(RoutineStore())
    return RoutineScheduler(store, brief_executor)
