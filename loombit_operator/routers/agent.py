"""
Router del agente autónomo de Loombit.

Endpoints:
  POST   /agent/run                — lanza una tarea nueva
  GET    /agent/runs               — lista de runs (filtrables por status)
  GET    /agent/runs/{run_id}      — detalle completo de un run
  POST   /agent/runs/{run_id}/approve — aprueba una acción pendiente y reanuda
  GET    /agent/tools              — catálogo de tools registradas

El agente corre de forma síncrona en el thread del request. Para producción
se puede mover a un BackgroundTask o Celery; la interfaz del router no cambia.
"""
from __future__ import annotations

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel

from ..agent import AgentLoop, AgentRun, AgentStatus
from ..agent.run import AgentStore
from ..tools import tool_registry

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agent", tags=["agent"])

# ── Shared instances (creados una sola vez por proceso) ──────────────────────
# AgentStore y AgentLoop se instancian aquí para reutilizarlos entre requests.
# En tests se pueden reemplazar con dependency injection si hace falta.

_store: AgentStore | None = None
_loop:  AgentLoop  | None = None


def _get_store() -> AgentStore:
    global _store
    if _store is None:
        _store = AgentStore()
    return _store


def _get_loop() -> AgentLoop:
    global _loop
    if _loop is None:
        _loop = AgentLoop(store=_get_store())
    return _loop


# ── Modelos Pydantic ──────────────────────────────────────────────────────────

class RunRequest(BaseModel):
    task: str
    max_steps: int = 20
    profile: str = "administrativo"


class ApproveRequest(BaseModel):
    comment: str = ""


class RunResponse(BaseModel):
    id: str
    task: str
    status: str
    step_count: int
    result: str
    error: str
    pending_approval: dict
    created_at: str
    updated_at: str
    completed_at: str

    @classmethod
    def from_run(cls, run: AgentRun) -> "RunResponse":
        return cls(**run.snapshot())

    model_config = {"from_attributes": True}


class RunDetailResponse(RunResponse):
    messages: list[dict]
    steps: list[dict]

    @classmethod
    def from_run(cls, run: AgentRun) -> "RunDetailResponse":  # type: ignore[override]
        data = run.to_dict()
        data.pop("max_steps", None)
        return cls(
            id=data["id"],
            task=data["task"],
            status=data["status"],
            step_count=len(data.get("steps", [])),
            result=data.get("result", ""),
            error=data.get("error", ""),
            pending_approval=data.get("pending_approval", {}),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            completed_at=data.get("completed_at", ""),
            messages=data.get("messages", []),
            steps=data.get("steps", []),
        )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/run", response_model=RunResponse, summary="Lanzar una tarea al agente")
async def start_run(body: RunRequest) -> RunResponse:
    """
    Lanza el agente con la tarea dada.
    Bloquea hasta que el agente completa, falla o necesita aprobación.
    """
    loop = _get_loop()
    try:
        run = loop.run(body.task)
    except Exception as exc:
        logger.exception("Error lanzando agente: %s", exc)
        raise HTTPException(status_code=500, detail=f"Error interno del agente: {exc}") from exc
    return RunResponse.from_run(run)


@router.get("/runs", response_model=list[RunResponse], summary="Listar runs del agente")
async def list_runs(
    status: Annotated[str | None, Query(description="Filtrar por status")] = None,
) -> list[RunResponse]:
    """Lista todos los runs, opcionalmente filtrados por status."""
    store = _get_store()
    agent_status = None
    if status:
        try:
            agent_status = AgentStatus(status)
        except ValueError as exc:
            valid = [s.value for s in AgentStatus]
            raise HTTPException(
                status_code=400,
                detail=f"Status inválido '{status}'. Válidos: {valid}",
            ) from exc
    runs = store.list(status=agent_status)
    return [RunResponse.from_run(r) for r in runs]


@router.get("/runs/{run_id}", response_model=RunDetailResponse, summary="Detalle de un run")
async def get_run(run_id: str) -> RunDetailResponse:
    """Devuelve el estado completo de un run, incluyendo historial de mensajes y pasos."""
    store = _get_store()
    try:
        run = store.get(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return RunDetailResponse.from_run(run)


@router.post(
    "/runs/{run_id}/approve",
    response_model=RunResponse,
    summary="Aprobar acción pendiente y reanudar",
)
async def approve_run(run_id: str, body: ApproveRequest = Body(default=ApproveRequest())) -> RunResponse:
    """
    Aprueba la acción que está esperando confirmación humana y reanuda el agente.
    Solo funciona si el run está en status 'pending_approval'.
    """
    loop = _get_loop()
    store = _get_store()

    try:
        run = store.get(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if run.status != AgentStatus.PENDING_APPROVAL:
        raise HTTPException(
            status_code=409,
            detail=f"El run no está en pending_approval (status={run.status})",
        )

    if body.comment:
        # Añadir comentario del humano al historial para que el LLM lo vea
        run.messages.append({
            "role": "user",
            "content": f"[Aprobación concedida] {body.comment}",
        })
        store.save_run(run)

    try:
        run = loop.resume(run_id)
    except Exception as exc:
        logger.exception("Error reanudando agente run=%s: %s", run_id, exc)
        raise HTTPException(status_code=500, detail=f"Error al reanudar: {exc}") from exc

    return RunResponse.from_run(run)


@router.get("/tools", summary="Catálogo de tools registradas")
async def list_tools() -> dict:
    """Devuelve el catálogo completo de tools disponibles para el agente."""
    return tool_registry.snapshot()


@router.get("/status", summary="Estado del subsistema de agente")
async def agent_status() -> dict:
    """Resumen rápido: store + tools."""
    store = _get_store()
    return {
        "store": store.snapshot(),
        "tools": tool_registry.snapshot(),
    }
