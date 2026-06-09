"""
routers/fabrica.py — API de la Fábrica de Skills (Skill X, auto-autoría gobernada).

Endpoints:
- POST /fabrica/ciclo                       → corre un ciclo (detectar→redactar→validar→proponer)
- GET  /fabrica/propuestas?estado=          → lista de propuestas (pendientes por defecto)
- GET  /fabrica/propuestas/{id}             → propuesta completa (con código y veredicto)
- POST /fabrica/propuestas/{id}/aprobar     → GATE HUMANO: aprueba, materializa y registra la tool
- POST /fabrica/propuestas/{id}/descartar   → GATE HUMANO: descarta (queda en el linaje)
- GET  /fabrica/estado                      → snapshot del store + manifest de la skill

La aprobación es el único punto que toca el sistema en vivo, y solo por acción humana explícita.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException

from ..fabrica.ciclo import ejecutar_ciclo
from ..fabrica.materializar import cargar_tools_aprobadas, escribir_tool_aprobada
from ..fabrica.modelos import EstadoPropuesta, PropuestaSkill
from ..fabrica.oportunidades import OportunidadStore
from ..fabrica.propuesta import PropuestaStore

router = APIRouter(prefix="/fabrica", tags=["fabrica"])


def _resumen(p: PropuestaSkill) -> dict[str, Any]:
    return {
        "id": p.id,
        "estado": p.estado.value,
        "fitness": p.fitness,
        "tipo": p.necesidad.tipo.value,
        "necesidad": p.necesidad.titulo,
        "tool": p.borrador.nombre,
        "descripcion": p.borrador.descripcion,
        "puertas_ok": p.veredicto.ok,
        "fallos": p.veredicto.fallos,
        "created_at": p.created_at,
    }


@router.post("/ciclo")
def correr_ciclo(max_necesidades: int = 3, max_intentos: int = 3) -> dict[str, Any]:
    """Corre un ciclo completo. Usa la memoria/runs reales y el coder local. No aplica nada."""
    return ejecutar_ciclo(max_necesidades=max_necesidades, max_intentos=max_intentos)


@router.get("/propuestas")
def listar_propuestas(estado: str | None = None) -> dict[str, Any]:
    store = PropuestaStore()
    filtro = EstadoPropuesta(estado) if estado else None
    props = store.list(filtro)
    return {"count": len(props), "propuestas": [_resumen(p) for p in props]}


@router.get("/propuestas/{propuesta_id}")
def ver_propuesta(propuesta_id: str) -> dict[str, Any]:
    try:
        return PropuestaStore().get(propuesta_id).to_dict()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/propuestas/{propuesta_id}/aprobar")
def aprobar_propuesta(propuesta_id: str, nota: str = Body("", embed=True)) -> dict[str, Any]:
    """GATE HUMANO. Aprueba → materializa el código en cuarentena → lo registra en vivo."""
    store = PropuestaStore()
    try:
        prop = store.aprobar(propuesta_id, nota)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        archivo = escribir_tool_aprobada(prop)
        registradas = cargar_tools_aprobadas(store=store)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"no se pudo materializar: {exc}") from exc
    return {
        "ok": True,
        "id": prop.id,
        "estado": prop.estado.value,
        "tool": prop.borrador.nombre,
        "archivo": str(archivo),
        "registradas": registradas,
    }


@router.post("/propuestas/{propuesta_id}/descartar")
def descartar_propuesta(propuesta_id: str, nota: str = Body("", embed=True)) -> dict[str, Any]:
    """GATE HUMANO. Descarta la propuesta (queda en el linaje como peldaño)."""
    store = PropuestaStore()
    try:
        prop = store.descartar(propuesta_id, nota)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "id": prop.id, "estado": prop.estado.value}


@router.post("/reparar")
def proponer_reparacion(
    archivo: str = Body(..., embed=True),
    instruccion: str = Body(..., embed=True),
    validar_tests: bool = Body(False, embed=True),
) -> dict[str, Any]:
    """Propone una mejora de un fichero EN USO como diff validado (el coder local). NO escribe nada:
    es una propuesta para revisar y aplicar en una rama. Gate sagrado sobre el código en uso.
    Con `validar_tests=true` corre además los tests contra el parche en un repo aislado (más lento).
    """
    from ..fabrica.reparar import proponer_parche

    resultado = proponer_parche(archivo, instruccion, validar_tests=validar_tests)
    if resultado is None:
        raise HTTPException(status_code=502, detail="el coder no produjo un parche usable")
    return resultado


@router.post("/chat")
def chat_fabrica(
    mensaje: str = Body(..., embed=True),
    historial: list[dict[str, Any]] = Body(default=[], embed=True),
) -> dict[str, Any]:
    """Habla con la Fábrica en lenguaje natural. El 14B ENTIENDE la intención (no depende de palabras
    clave) y conversa fundamentándose en el estado real; con red de seguridad determinista si el modelo
    no responde. `historial` (opcional) da contexto multi-turno. Canal de la Sala de la Fábrica."""
    from ..fabrica.chat import responder

    return responder(mensaje, historial=historial)


@router.post("/gepa")
def correr_gepa(max_intentos: int = Body(2, embed=True)) -> dict[str, Any]:
    """GEPA real: reflexiona sobre trazas + escenarios fallados y propone una EDICIÓN del prompt del
    agente, VALIDADA contra el eval de comportamiento (F1-F8). Devuelve diff + scores. NO escribe nada:
    el humano lo aplica en una rama (gate sagrado · andamiaje, no pesos). Necesita el 14B (lento).
    """
    from ..fabrica.gepa import optimizar_prompt

    return optimizar_prompt(max_intentos=max_intentos)


@router.get("/gepa")
def gepa_ultimo() -> dict[str, Any]:
    """Último resultado de GEPA guardado (para pintarlo en la Sala sin volver a correr el modelo)."""
    from ..fabrica.gepa import ultimo_resultado

    return ultimo_resultado() or {"ok": False, "resumen": "GEPA aún no se ha corrido."}


@router.get("/estrategia")
def estrategia_fabrica() -> dict[str, Any]:
    """Destila las señales del radar en vías de producto/monetización para Loombit (instructor LLM)."""
    from ..fabrica.estrategia import sintetizar_estrategia

    return sintetizar_estrategia(OportunidadStore().list())


@router.post("/investigar")
def investigar_oportunidad(
    titulo: str = Body(..., embed=True), url: str = Body("", embed=True)
) -> dict[str, Any]:
    """Investiga una señal del radar: la lee (si puede) y dice qué es y cómo traerla a Loombit."""
    from ..fabrica.estrategia import analizar_oportunidad

    return analizar_oportunidad(titulo, url)


@router.get("/marcar")
def marcar_codigo() -> dict[str, Any]:
    """Salud del código en uso: bugs (ruff-B), TODO, ficheros >400 líneas, prompts, huecos de eval."""
    from ..fabrica.interno import marcar

    necs = marcar()
    return {
        "count": len(necs),
        "items": [
            {
                "titulo": n.titulo,
                "tipo": n.tipo.value,
                "prioridad": n.prioridad,
                "ref": n.procedencia[0] if n.procedencia else "",
            }
            for n in necs
        ],
    }


@router.get("/oportunidades")
def listar_oportunidades(estado: str | None = None) -> dict[str, Any]:
    """Hallazgos del radar externo (competencia/mercado/tech/normativa) + meta, para tu revisión."""
    store = OportunidadStore()
    return {"snapshot": store.snapshot(), "items": store.list(estado)}


@router.post("/oportunidades/{clave}/atendida")
def atender_oportunidad(clave: str) -> dict[str, Any]:
    """Marca un hallazgo como atendido (lo has llevado al roadmap o descartado)."""
    return {"ok": OportunidadStore().marcar_atendida(clave)}


@router.get("/estado")
def estado_fabrica() -> dict[str, Any]:
    snap = PropuestaStore().snapshot()
    manifest: dict[str, Any] | None = None
    try:
        from ..skill_loader import SkillManifestLoader

        registro = SkillManifestLoader().load()
        manifest = registro.get("fabrica_de_skills").to_dict()
    except Exception:  # noqa: BLE001 — el estado no debe romper si el manifest no carga
        manifest = None
    return {"store": snap, "skill": manifest}
