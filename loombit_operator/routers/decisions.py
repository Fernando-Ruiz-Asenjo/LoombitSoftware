"""
routers/decisions.py — API de «Loombit Decide» (LD-0 + LD-1 + LD-2).

GET  /decisions               → la COLA (decisiones pendientes) + su spec de UI gobernada (validada)
GET  /decisions/{id}          → una decisión + su decision_card spec
GET  /decisions/{id}/spec     → solo la spec validada (lo que el renderer pinta)
POST /decisions/{id}/resolve  → el humano elige una opción; si es APROBAR, lanza la acción preparada
                                al agente (el efecto externo lo retiene el gate PENDING_APPROVAL)
POST /decisions/{id}/dismiss  → retira la decisión de la cola
POST /decisions/sembrar-cobros → LD-2: compone decisiones de cobro desde las cuentas vencidas

El backend SOLO emite specs validadas (`validated_spec`): nunca sale del servidor una spec con HTML/JS.
Separación de Autoridades: resolver «aprobar» NO envía nada — crea la tarea del agente, que prepara el
borrador y pasa por el gate humano. El LLM no está en el camino del efecto.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from ..decisions import DecisionStore, OptionKind
from ..ui_spec import cola_to_spec, decision_to_spec

router = APIRouter(prefix="/decisions", tags=["loombit-decide"])


class Resolucion(BaseModel):
    option_id: str


def _lanzar_accion(task: str, background_tasks: BackgroundTasks) -> str:
    """Crea un AgentRun con la tarea preparada y lo ejecuta en background. El efecto externo (enviar
    el correo) lo RETIENE el gate `PENDING_APPROVAL` del agente — aquí no se envía nada. Seam
    reemplazable en tests (el golden del cableado no necesita el LLM)."""
    from ..agent import AgentLoop
    from ..agent.run import AgentStore

    loop = AgentLoop(store=AgentStore())
    run = loop.create(task)
    background_tasks.add_task(loop.execute_run, run.id)
    return run.id


@router.get("")
def cola() -> dict:
    """La cola de decisiones pendientes + la spec de UI gobernada que la pinta."""
    s = DecisionStore()
    pendientes = s.cola()
    return {
        "decisions": [d.to_dict() for d in pendientes],
        "spec": cola_to_spec(pendientes),
        "count": len(pendientes),
    }


@router.post("/sembrar-cobros")
def sembrar_cobros() -> dict:
    """LD-2: compone una decisión por cada cobro vencido (cifras por código, Ley 3/2004) y la encola.
    Idempotente: no duplica una decisión para una cuenta que ya tiene una en la cola/historial."""
    from ..cuentas_cobrar import CuentasCobrarStore
    from ..decisions_cobros import decisiones_de_cobros

    s = DecisionStore()
    existentes = {d.source.get("cuenta_id") for d in s.list() if d.source.get("cuenta_id")}
    nuevas: list[str] = []
    for d in decisiones_de_cobros(CuentasCobrarStore().vencidas()):
        if d.source.get("cuenta_id") in existentes:
            continue
        s.add(d)
        nuevas.append(d.id)
    return {"creadas": len(nuevas), "ids": nuevas}


@router.get("/{decision_id}")
def obtener(decision_id: str) -> dict:
    s = DecisionStore()
    try:
        d = s.get(decision_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"decisión no encontrada: {decision_id}")
    return {"decision": d.to_dict(), "spec": decision_to_spec(d)}


@router.get("/{decision_id}/spec")
def spec(decision_id: str) -> dict:
    s = DecisionStore()
    try:
        d = s.get(decision_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"decisión no encontrada: {decision_id}")
    return decision_to_spec(d)


@router.post("/{decision_id}/resolve")
def resolver(decision_id: str, body: Resolucion, background_tasks: BackgroundTasks) -> dict:
    s = DecisionStore()
    try:
        d = s.resolve(decision_id, body.option_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"decisión no encontrada: {decision_id}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # LD-2: si la opción elegida es APROBAR y la decisión trae una acción preparada, se lanza al
    # agente (que prepara el borrador y lo deja en el gate). El envío real NUNCA sale de aquí.
    run_id = ""
    opcion = next((o for o in d.options if o.id == body.option_id), None)
    if opcion is not None and opcion.kind == OptionKind.APROBAR:
        task = d.payload.get("agent_task")
        if isinstance(task, str) and task.strip():
            run_id = _lanzar_accion(task, background_tasks)

    return {"ok": True, "decision": d.to_dict(), "run_id": run_id}


@router.post("/{decision_id}/dismiss")
def descartar(decision_id: str) -> dict:
    s = DecisionStore()
    try:
        d = s.dismiss(decision_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"decisión no encontrada: {decision_id}")
    return {"ok": True, "decision": d.to_dict()}
