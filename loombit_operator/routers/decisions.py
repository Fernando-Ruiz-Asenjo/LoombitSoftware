"""
routers/decisions.py — API de «Loombit Decide» (LD-0 + LD-1).

GET  /decisions              → la COLA (decisiones pendientes) + su spec de UI gobernada (validada)
GET  /decisions/{id}         → una decisión + su decision_card spec
GET  /decisions/{id}/spec    → solo la spec validada (lo que el renderer pinta)
POST /decisions/{id}/resolve → el humano elige una opción (registra la decisión; el efecto lo cablea LD-2)
POST /decisions/{id}/dismiss → retira la decisión de la cola

El backend SOLO emite specs validadas (`validated_spec`): nunca sale del servidor una spec con HTML/JS.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..decisions import DecisionStore
from ..ui_spec import cola_to_spec, decision_to_spec

router = APIRouter(prefix="/decisions", tags=["loombit-decide"])


class Resolucion(BaseModel):
    option_id: str


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
def resolver(decision_id: str, body: Resolucion) -> dict:
    s = DecisionStore()
    try:
        d = s.resolve(decision_id, body.option_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"decisión no encontrada: {decision_id}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True, "decision": d.to_dict()}


@router.post("/{decision_id}/dismiss")
def descartar(decision_id: str) -> dict:
    s = DecisionStore()
    try:
        d = s.dismiss(decision_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"decisión no encontrada: {decision_id}")
    return {"ok": True, "decision": d.to_dict()}
