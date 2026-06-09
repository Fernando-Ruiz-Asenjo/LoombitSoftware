"""
ciclo.py — orquesta la Fábrica: detectar → redactar → validar → proponer (con auto-reparación).

El bucle por necesidad (patrón OpenEvolve/Voyager): redacta un borrador, lo pasa por el arnés y,
si una puerta falla, REALIMENTA ese fallo al coder para el siguiente intento (canal de artefactos).
Si tras N intentos pasa, se guarda como PROPUESTA PENDIENTE (espera el gate humano). Si no, el mejor
intento se guarda como FALLIDA: es el linaje (DGM/ADAS), un peldaño con su fitness.

La Fábrica NUNCA aplica nada: solo propone. La orquestación es determinista; la creatividad la pone
el coder, pero el validador (verdad de tierra) decide qué es proponible. Sin chorradas que se cuelen.
"""

from __future__ import annotations

from typing import Any

from .autoria import redactar
from .fuentes import FuenteRegistry, registro_por_defecto
from .modelos import EstadoPropuesta, Fuente, Necesidad, PropuestaSkill, TipoNecesidad, Veredicto
from .oportunidades import OportunidadStore
from .propuesta import PropuestaStore
from .validacion import validar


def _feedback(veredicto: Veredicto) -> str:
    """Resume las puertas en rojo para realimentar al coder (auto-reparación)."""
    return " | ".join(f"{n}: {veredicto.puertas[n]['detalle']}" for n in veredicto.fallos)


def _atacar_necesidad(
    necesidad: Necesidad, max_intentos: int, llm: Any, playbook: Any = None
) -> tuple[PropuestaSkill | None, dict[str, Any]]:
    """Intenta hasta `max_intentos` redactar+validar una tool para la necesidad."""
    feedback = ""
    mejor: tuple[Any, Veredicto] | None = None
    traza: list[dict[str, Any]] = []

    for intento in range(1, max_intentos + 1):
        borrador = redactar(necesidad, feedback=feedback, llm=llm, playbook=playbook)
        if borrador is None:
            traza.append({"intento": intento, "resultado": "el coder no produjo una tool usable"})
            break
        veredicto = validar(borrador)
        traza.append(
            {
                "intento": intento,
                "tool": borrador.nombre,
                "ok": veredicto.ok,
                "fallos": veredicto.fallos,
            }
        )
        if veredicto.ok:
            prop = PropuestaSkill(necesidad=necesidad, borrador=borrador, veredicto=veredicto)
            return prop, {"estado": "propuesta", "intentos": intento, "traza": traza}
        if mejor is None or veredicto.ok or len(veredicto.fallos) < len(mejor[1].fallos):
            mejor = (borrador, veredicto)
        feedback = _feedback(veredicto)

    # No pasó: guarda el mejor peldaño como FALLIDA (linaje).
    if mejor is not None:
        prop = PropuestaSkill(
            necesidad=necesidad,
            borrador=mejor[0],
            veredicto=mejor[1],
            estado=EstadoPropuesta.FALLIDA,
        )
        return prop, {"estado": "fallida", "intentos": len(traza), "traza": traza}
    return None, {"estado": "sin_borrador", "intentos": len(traza), "traza": traza}


def ejecutar_ciclo(
    *,
    max_necesidades: int = 3,
    max_intentos: int = 3,
    llm: Any = None,
    memoria: Any = None,
    store_runs: Any = None,
    store_prop: PropuestaStore | None = None,
    store_op: OportunidadStore | None = None,
    registro: FuenteRegistry | None = None,
    fuentes: list[Fuente] | None = None,
    http_get: Any = None,
    playbook: Any = None,
) -> dict[str, Any]:
    """Corre un ciclo del MOTOR MULTI-FUENTE: detecta oportunidades de TODO el abanico (dentro: runs;
    fuera: la Red; meta), y para cada una elige el objetivo correcto:
    - TOOL  → la redacta, la valida con el arnés y la PROPONE (PropuestaStore, con gate).
    - resto → la guarda como HALLAZGO citado para tu revisión (OportunidadStore). No inventa código.
    No aplica nada: el humano decide. `fuentes`/`http_get` permiten correr offline en tests."""
    registro = registro or registro_por_defecto()
    store = store_prop or PropuestaStore()
    store_op = store_op or OportunidadStore()

    oportunidades = registro.detectar(
        fuentes=fuentes,
        memoria=memoria,
        store_runs=store_runs,
        store_prop=store,
        http_get=http_get,
    )
    tool_needs = [o for o in oportunidades if o.tipo == TipoNecesidad.TOOL]
    hallazgos = [o for o in oportunidades if o.tipo != TipoNecesidad.TOOL]

    propuestas_nuevas: list[str] = []
    detalle_tools: list[dict[str, Any]] = []
    for nec in tool_needs[:max_necesidades]:
        prop, detalle = _atacar_necesidad(nec, max_intentos, llm, playbook)
        if prop is not None:
            store.add(prop)
            if prop.estado == EstadoPropuesta.PENDIENTE:
                propuestas_nuevas.append(prop.id)
        detalle_tools.append(
            {"necesidad": nec.titulo, "propuesta_id": prop.id if prop else None, **detalle}
        )

    nuevos_hallazgos = store_op.registrar(hallazgos)

    return {
        "fuentes": [f.value for f in (fuentes or registro.fuentes())],
        "oportunidades_detectadas": len(oportunidades),
        "tools": {
            "necesidades": len(tool_needs),
            "propuestas_pendientes_nuevas": propuestas_nuevas,
            "pendientes_totales": len(store.list(EstadoPropuesta.PENDIENTE)),
            "detalle": detalle_tools,
        },
        "hallazgos_red_meta": {
            "nuevos": len(nuevos_hallazgos),
            "muestra": [
                {
                    "titulo": h.titulo[:120],
                    "fuente": h.fuente.value,
                    "fuente_url": h.procedencia[0] if h.procedencia else "",
                }
                for h in nuevos_hallazgos[:8]
            ],
        },
    }
