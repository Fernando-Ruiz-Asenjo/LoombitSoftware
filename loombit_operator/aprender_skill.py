"""
aprender_skill.py — "Enséñale" (S2, paridad Gemini Spark). Núcleo blanco.

De una orden en lenguaje natural ("cada lunes a las 9 mándame el resumen de cobros") a una
**Routine** reutilizable y auto-disparada. El horario lo dispone el CÓDIGO de forma
DETERMINISTA (tabla de frases español→cron); el LLM no inventa el disparador. La tarea se
ejecuta luego por el agent loop y **todo efecto externo PAUSA para aprobación** (ASSISTED):
nunca se auto-envía. No asume dominio (sirve igual para admin, soporte o lo que sea).

Estado: 🟢 parseo + creación (reproducible, unit-tested). La ejecución real de la tarea va por
`routine_executors.agente_executor` (agent loop + LLM): su corrida en vivo es 🟡.
"""

from __future__ import annotations

import re

from .routines import CronSchedule, Routine, RoutineStore
from .skills import SkillSafetyClass

# Evento sin hora concreta ("cuando entre…") → sondeo prudente; la condición la juzga la tarea.
DEFAULT_POLL = "*/15 * * * *"

_DIAS = {
    "lunes": 1,
    "martes": 2,
    "miércoles": 3,
    "miercoles": 3,
    "jueves": 4,
    "viernes": 5,
    "sábado": 6,
    "sabado": 6,
    "domingo": 0,
}
_DIAS_NOMBRE = {
    1: "lunes",
    2: "martes",
    3: "miércoles",
    4: "jueves",
    5: "viernes",
    6: "sábado",
    0: "domingo",
}


def _hora(texto: str) -> tuple[int, int] | None:
    """Extrae (hora, minuto) de frases como 'a las 9', 'a las 9:30', 'a las 21h', '18:00',
    'a las 5 de la tarde'. None si no hay hora explícita ni franja ('mañana'/'tarde'/'noche')."""
    t = texto.lower()
    m = re.search(r"a\s+las\s+(\d{1,2})(?:[:.h](\d{2}))?", t) or re.search(
        r"\b(\d{1,2}):(\d{2})\b", t
    )
    if not m:
        if "mañana" in t:
            return 8, 0
        if "tarde" in t:
            return 16, 0
        if "noche" in t:
            return 20, 0
        return None
    h = int(m.group(1))
    mi = int(m.group(2)) if m.group(2) else 0
    if re.search(r"\b(pm|de la tarde|de la noche)\b", t) and h < 12:
        h += 12
    if h > 23 or mi > 59:
        return None
    return h, mi


def interpretar_horario(texto: str) -> dict | None:
    """Texto español → {'cron': '0 9 * * 1', 'humano': '…'} de forma DETERMINISTA, o None si no
    hay horario explícito (el llamante lo tratará como evento con sondeo). Soporta: 'cada N
    minutos', 'cada hora', 'cada N horas', días de la semana (con o sin hora), 'cada día/todos los
    días/cada mañana…', y una hora suelta ('a las 18:00' = cada día a esa hora)."""
    t = (texto or "").lower()

    m = re.search(r"cada\s+(\d+)\s*(?:minutos?|min)\b", t)
    if m:
        n = max(1, min(59, int(m.group(1))))
        return {"cron": f"*/{n} * * * *", "humano": f"cada {n} minuto(s)"}
    if re.search(r"\bcada\s+hora\b", t):
        return {"cron": "0 * * * *", "humano": "cada hora"}
    m = re.search(r"cada\s+(\d+)\s*horas\b", t)
    if m:
        n = max(1, min(23, int(m.group(1))))
        return {"cron": f"0 */{n} * * *", "humano": f"cada {n} horas"}

    dias = sorted({d for nombre, d in _DIAS.items() if re.search(rf"\b{nombre}\b", t)})
    hora = _hora(t)
    if dias:
        h, mi = hora or (9, 0)
        dow = ",".join(str(d) for d in dias)
        nombres = ", ".join(_DIAS_NOMBRE[d] for d in dias)
        return {"cron": f"{mi} {h} * * {dow}", "humano": f"los {nombres} a las {h:02d}:{mi:02d}"}

    if re.search(
        r"\b(cada d[ií]a|todos los d[ií]as|a diario|cada (mañana|tarde|noche)|diariamente)\b", t
    ):
        h, mi = hora or (8, 0)
        return {"cron": f"{mi} {h} * * *", "humano": f"cada día a las {h:02d}:{mi:02d}"}

    if hora:
        h, mi = hora
        return {"cron": f"{mi} {h} * * *", "humano": f"cada día a las {h:02d}:{mi:02d}"}

    return None


def _nombre_desde(texto: str) -> str:
    """Nombre corto y legible desde la orden (primeras palabras), para la lista de skills."""
    limpio = re.sub(r"\s+", " ", texto.strip())
    corto = " ".join(limpio.split(" ")[:7])[:60].strip(" .,")
    return corto or "Skill enseñada"


def crear_skill_desde_texto(texto: str, store: RoutineStore | None = None) -> dict:
    """Crea (y persiste) una Routine desde la orden en lenguaje natural. Devuelve la routine, el
    'entendido' para enseñárselo al usuario, el cron y si es por evento. ASSISTED: el efecto
    externo siempre se confirma."""
    texto = (texto or "").strip()
    if not texto:
        raise ValueError("texto vacío: no hay nada que enseñar")
    store = store or RoutineStore()

    horario = interpretar_horario(texto)
    if horario:
        cron, humano, evento = horario["cron"], horario["humano"], False
    else:
        cron, humano, evento = (
            DEFAULT_POLL,
            "en cuanto detecte la condición (sondeo cada 15 min)",
            True,
        )

    routine = Routine(
        name=_nombre_desde(texto),
        schedule=CronSchedule(cron),
        objective=texto,
        safety=SkillSafetyClass.ASSISTED,  # todo efecto externo PAUSA para tu aprobación
        output_kind="agente",
        enabled=True,
    )
    store.add(routine)
    entendido = (
        f"Entendí: {humano}. Prepararé «{texto}» y te lo dejaré listo para que lo apruebes "
        "antes de cualquier envío."
    )
    return {"routine": routine.to_dict(), "entendido": entendido, "cron": cron, "evento": evento}
