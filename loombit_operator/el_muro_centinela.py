"""
el_muro_centinela.py — el CENTINELA de El Muro: el miembro ALWAYS-ON del equipo de defensa.

El Muro (docs/EL_MURO.md) es el equipo que hace cumplir la Brújula. Casi todos sus miembros son
gate-time (commit/CI). El centinela es el que vigila 24/7: una Routine PASSIVE (read-only, sin
efecto externo) que comprueba a diario que las defensas siguen sanas —el radar fresco (<=45 días)
y la cadena de gobierno íntegra— y deja un recibo. No arregla ni decide nada (el LLM propone, El
Muro dispone): solo VIGILA y reporta lo que encuentra.

Diseño determinista y testeable: `salud_muro(...)` es PURA (recibe el resultado de los auditores
y devuelve el veredicto); `centinela_executor` la alimenta corriendo los auditores reales.
ADITIVO: no toca `routine_executors.py` (envuelve el scheduler por defecto), así que no pelea con
la deuda de tamaño de ese fichero.
"""

from __future__ import annotations

from datetime import datetime

from .routines import CronSchedule, Routine, RoutineStore
from .scheduler import RoutineScheduler
from .skills import SkillSafetyClass

CENTINELA_NOMBRE = "Centinela de El Muro"
CENTINELA_KIND = "centinela"


def salud_muro(
    radar_fallos: list[str],
    cadena_errores: list[str],
    n_senales: int,
    n_bloques: int,
) -> tuple[bool, list[str]]:
    """PURA: del resultado de los auditores deriva (sano, líneas de reporte).

    El LLM no interviene: es código determinista (El Muro dispone). `sano` es True solo si ni el
    radar ni la cadena tienen fallos.
    """
    lineas: list[str] = []
    if radar_fallos:
        lineas.append(f"RADAR FALLO ({len(radar_fallos)}): " + "; ".join(radar_fallos[:3]))
    else:
        lineas.append(f"RADAR OK: vivo y fresco ({n_senales} señales)")
    if cadena_errores:
        lineas.append(f"CADENA FALLO ({len(cadena_errores)}): " + "; ".join(cadena_errores[:3]))
    else:
        lineas.append(f"CADENA OK: íntegra ({n_bloques} bloques)")
    sano = not radar_fallos and not cadena_errores
    lineas.insert(0, "El Muro: SANO" if sano else "El Muro: ATENCIÓN")
    return sano, lineas


def _asegurar_scripts_importables() -> None:
    """Pone la raíz del repo en sys.path para importar `scripts.*` desde cualquier cwd."""
    import sys
    from pathlib import Path

    raiz = str(Path(__file__).resolve().parent.parent)
    if raiz not in sys.path:
        sys.path.insert(0, raiz)


def centinela_executor(routine: Routine, now: datetime) -> str:
    """Corre los auditores read-only (radar + cadena) y devuelve el reporte de salud.

    Sin efecto externo (PASSIVE). Cada chequeo va en su try: un fallo de importación o de lectura
    se REPORTA como hallazgo, no tumba al centinela (monitor robusto).
    """
    radar_fallos: list[str] = []
    cadena_errores: list[str] = []
    n_senales = n_bloques = 0
    try:
        _asegurar_scripts_importables()
        from scripts.auditoria_radar import auditar as _auditar_radar
        from scripts.auditoria_radar import cargar as _cargar_radar

        radar_fallos = _auditar_radar()
        n_senales = len(_cargar_radar())
    except Exception as exc:  # contenido: el monitor reporta, no revienta
        radar_fallos = [f"no se pudo auditar el radar: {exc!r}"]
    try:
        _asegurar_scripts_importables()
        from scripts.auditoria_cadena import cargar as _cargar_cadena
        from scripts.auditoria_cadena import verificar_cadena

        bloques = _cargar_cadena()
        n_bloques = len(bloques)
        cadena_errores = verificar_cadena(bloques)
    except Exception as exc:
        cadena_errores = [f"no se pudo verificar la cadena: {exc!r}"]
    _, lineas = salud_muro(radar_fallos, cadena_errores, n_senales, n_bloques)
    return "\n".join(lineas)


def centinela_routine() -> Routine:
    """Plantilla: el centinela corre a diario a las 07:00 (Europe/Madrid).

    PASSIVE = read-only, auto-completa sin gate (no tiene efecto externo que aprobar).
    """
    return Routine(
        name=CENTINELA_NOMBRE,
        schedule=CronSchedule("0 7 * * *", tz="Europe/Madrid"),
        objective=(
            "Vigila la salud de El Muro (read-only): radar fresco (<=45 días) y cadena de "
            "gobierno íntegra. Deja recibo. No arregla ni decide nada: solo vigila."
        ),
        safety=SkillSafetyClass.PASSIVE,
        output_kind=CENTINELA_KIND,
        enabled=True,
    )


def ensure_centinela(store: RoutineStore) -> RoutineStore:
    """Siembra el centinela si falta (idempotente)."""
    if CENTINELA_NOMBRE not in {r.name for r in store.list()}:
        store.add(centinela_routine())
    return store


def build_scheduler_con_centinela(store: RoutineStore | None = None) -> RoutineScheduler:
    """Scheduler por defecto + el centinela always-on.

    Envuelve el dispatcher por defecto sin tocar `routine_executors.py`: si la routine es del
    centinela la corre aquí, si no delega en `default_executor`. `store=None` usa el store real
    (producción); los tests inyectan uno temporal.
    """
    from .routine_executors import default_executor, ensure_default_routines

    base = store if store is not None else RoutineStore()
    ensure_centinela(ensure_default_routines(base))

    def _dispatch(routine: Routine, now: datetime) -> str:
        if routine.output_kind == CENTINELA_KIND:
            return centinela_executor(routine, now)
        return default_executor(routine, now)

    return RoutineScheduler(base, _dispatch)
