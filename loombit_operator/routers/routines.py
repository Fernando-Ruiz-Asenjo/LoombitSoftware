"""
routers/routines.py — API de Routines (agentes proactivos programados).

Endpoints:
- GET  /routines            → lista de rutinas (seedea el Brief diario si está vacío)
- POST /routines/tick       → dispara las rutinas que toquen ahora (cron)
- POST /routines/{id}/run   → fuerza una rutina ahora (demo/manual, ignora el cron)

El ejecutor real usa el LLM instructor (14B). Ver `docs/ROUTINES_LOOMBIT.md`.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..routine_executors import brief_executor, ensure_default_routines
from ..routines import RoutineNotFoundError, RoutineStore
from ..scheduler import RoutineScheduler

router = APIRouter(prefix="/routines", tags=["routines"])


def _store() -> RoutineStore:
    return ensure_default_routines(RoutineStore())


@router.get("")
def list_routines() -> dict:
    return _store().snapshot()


@router.post("/tick")
def tick_now() -> dict:
    store = _store()
    scheduler = RoutineScheduler(store, brief_executor)
    receipts = scheduler.tick()
    return {"fired": len(receipts), "receipts": [r.to_dict() for r in receipts]}


@router.post("/{routine_id}/run")
def run_routine(routine_id: str) -> dict:
    store = _store()
    try:
        routine = store.get(routine_id)
    except RoutineNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"routine no encontrada: {routine_id}") from exc
    scheduler = RoutineScheduler(store, brief_executor)
    return scheduler.run_routine(routine).to_dict()
