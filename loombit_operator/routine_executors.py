"""
routine_executors.py — ejecutores concretos para las Routines + armado por defecto.

El motor (`scheduler.py`) es neutro y recibe un executor inyectado. Aquí vive el
executor real basado en el LLM instructor (14B) y el armado del scheduler por defecto
(store seedeado con el Brief diario). Separado para evitar import circular con el router.
"""

from __future__ import annotations

from datetime import datetime

from .llm import LLMClient
from .routines import CronSchedule, Routine, RoutineStore, brief_diario_routine
from .scheduler import RoutineScheduler
from .skills import SkillSafetyClass

_BRIEF_SYSTEM = (
    "Eres Loombit, operador administrativo local. Responde SIEMPRE en español, en un "
    "brief de máximo 5 líneas, en lenguaje natural, sin JSON ni markdown."
)

_MEJORA_SYSTEM = (
    "Eres el ingeniero de mejora continua de Loombit. Te paso el estado de auto-chequeo "
    "(qué evals están verdes/rojos y qué huecos quedan sin eval). Devuelve, en español y "
    "conciso: (1) 2-3 PRÓXIMOS PASOS sólidos y concretos para cerrar los huecos, y (2) 2-3 "
    "TEMAS A INVESTIGAR en internet (métodos/papers/patrones) para avanzar con método, no por "
    "suerte. Sé específico y honesto; no inventes que algo está hecho."
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


def mejora_continua_routine() -> Routine:
    """Routine de mejora continua: lunes 09:00. Codifica el 'proponer soluciones + investigar
    métodos' para que el sistema avance solo, sin que haya que pedírselo. PASSIVE (solo informa)."""
    return Routine(
        name="Mejora continua",
        schedule=CronSchedule("0 9 * * 1"),
        objective=(
            "Revisa el auto-chequeo y los huecos del eval-set; propón los próximos pasos sólidos "
            "y los temas a investigar en internet para seguir avanzando con método."
        ),
        safety=SkillSafetyClass.PASSIVE,
        output_kind="mejora",
    )


def mejora_continua_executor(routine: Routine, now: datetime) -> str:
    """Codifica el bucle de mejora: parte del estado REAL del sistema (auto-chequeo + huecos) y
    pide al LLM propuestas concretas + temas a investigar. La búsqueda web autónoma es el siguiente
    enganche (necesita una tool de búsqueda cableada a la routine); por ahora nombra los temas."""
    try:
        from .selfcheck import run_selfcheck

        chk = run_selfcheck()
        estado = (
            f"Auto-chequeo: {chk.get('verdes', 0)}/{chk.get('total', 0)} verdes. "
            f"Rojos: {chk.get('fallos') or 'ninguno'}. "
            f"Huecos sin eval: {chk.get('pendientes_sin_eval') or 'ninguno'}."
        )
    except Exception as exc:
        estado = f"(No se pudo leer el auto-chequeo: {exc!r})"

    messages = [
        {"role": "system", "content": _MEJORA_SYSTEM},
        {"role": "user", "content": f"{routine.objective}\n\nEstado actual:\n{estado}"},
    ]
    return LLMClient().chat(messages, max_tokens=400).content.strip()


def default_executor(routine: Routine, now: datetime) -> str:
    """Despacha al executor según el tipo de routine (un solo punto de entrada para el scheduler)."""
    if routine.output_kind == "mejora":
        return mejora_continua_executor(routine, now)
    return brief_executor(routine, now)


def ensure_default_routines(store: RoutineStore) -> RoutineStore:
    """Siembra las routines por defecto si faltan (Brief diario + Mejora continua)."""
    nombres = {r.name for r in store.list()}
    if "Brief diario" not in nombres:
        store.add(brief_diario_routine())
    if "Mejora continua" not in nombres:
        store.add(mejora_continua_routine())
    return store


def build_default_scheduler() -> RoutineScheduler:
    """Store seedeado + scheduler con el dispatcher de executors. Usado por el router y el daemon."""
    store = ensure_default_routines(RoutineStore())
    return RoutineScheduler(store, default_executor)
