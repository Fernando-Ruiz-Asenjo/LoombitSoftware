"""
Router del agente autónomo de Loombit.

Endpoints:
  POST   /agent/run                        — lanza una tarea nueva
  GET    /agent/runs                       — lista de runs (filtrables por status)
  GET    /agent/runs/{run_id}              — detalle completo de un run
  POST   /agent/runs/{run_id}/approve      — aprueba una acción pendiente y reanuda
  POST   /agent/runs/{run_id}/answer       — responde a una pregunta del agente
  POST   /agent/runs/{run_id}/cancel       — cancela un run activo
  GET    /agent/tools                      — catálogo de tools registradas

El agente corre de forma síncrona en el thread del request. Para producción
se puede mover a un BackgroundTask o Celery; la interfaz del router no cambia.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Body, HTTPException, Query
from pydantic import BaseModel

from ..agent import AgentLoop, AgentRun, AgentStatus
from ..agent.memory import get_memory
from ..agent.run import AgentStore
from ..tools import tool_registry

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agent", tags=["agent"])

# ── Shared instances (creados una sola vez por proceso) ──────────────────────
# AgentStore y AgentLoop se instancian aquí para reutilizarlos entre requests.
# En tests se pueden reemplazar con dependency injection si hace falta.

_store: AgentStore | None = None
_loop: AgentLoop | None = None


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


class AnswerRequest(BaseModel):
    answer: str


class RunResponse(BaseModel):
    id: str
    task: str
    status: str
    step_count: int
    result: str
    error: str
    pending_approval: dict
    pending_question: dict
    created_at: str
    updated_at: str
    completed_at: str

    @classmethod
    def from_run(cls, run: AgentRun) -> "RunResponse":
        snap = run.snapshot()
        snap.setdefault("pending_question", {})
        return cls(**snap)

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
            pending_question=data.get("pending_question", {}),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            completed_at=data.get("completed_at", ""),
            messages=data.get("messages", []),
            steps=data.get("steps", []),
        )


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/run", response_model=RunResponse, summary="Lanzar una tarea al agente")
async def start_run(body: RunRequest, background_tasks: BackgroundTasks) -> RunResponse:
    """
    Crea el run inmediatamente (status=running) y ejecuta el agente en background.
    Usar GET /agent/runs/{id} para seguir el estado (polling).
    """
    loop = _get_loop()
    try:
        run = loop.create(body.task, max_steps=body.max_steps, profile=body.profile)
        # Fricción cero: una cortesía pura ("hola", "gracias") se responde AL INSTANTE, sin gastar el
        # bucle ReAct del 14B (que en local son decenas de segundos de "Procesando…" para nada).
        from ..agent.smalltalk import respuesta_social

        social = respuesta_social(body.task)
        if social is not None:
            run.mark_completed(social)
            loop.store.save_run(run)
            return RunResponse.from_run(run)
        background_tasks.add_task(loop.execute_run, run.id)
    except Exception as exc:
        logger.exception("Error creando run: %s", exc)
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


def _invalidar_telar() -> None:
    """Aprobar/cancelar un run cambia lo que hay en la tela (p.ej. el nº de aprobaciones) → refresca."""
    try:
        from ..telar_cache import invalidate

        invalidate()
    except Exception:
        pass


@router.post(
    "/runs/{run_id}/approve",
    response_model=RunResponse,
    summary="Aprobar acción pendiente y reanudar",
)
async def approve_run(
    run_id: str,
    background_tasks: BackgroundTasks,
    body: ApproveRequest = Body(default=ApproveRequest()),
) -> RunResponse:
    """
    Aprueba la acción pendiente y reanuda el agente en background.
    Usar GET /agent/runs/{id} para seguir el estado (polling).
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
        run.messages.append(
            {
                "role": "user",
                "content": f"[Aprobación concedida] {body.comment}",
            }
        )
        store.save_run(run)

    # Aceptamos la aprobación de forma SÍNCRONA (run → running) y dejamos la ejecución de la tool
    # aprobada + la continuación del LLM para background. Así la respuesta ya NO devuelve el estado
    # viejo (pending_approval) y la UI no vuelve a pintar la misma tarjeta; hace polling al estado real.
    run = loop.accept_approval(run_id)
    _invalidar_telar()
    background_tasks.add_task(loop._resume_execute, run_id)
    return RunResponse.from_run(run)


@router.post("/approve-all", summary="Aprobar y lanzar TODAS las acciones pendientes")
async def approve_all(background_tasks: BackgroundTasks) -> dict:
    """Aprueba y ejecuta de una vez todas las acciones en espera (sin diálogos)."""
    store = _get_store()
    loop = _get_loop()
    pendientes = store.list(status=AgentStatus.PENDING_APPROVAL)
    ids = [r.id for r in pendientes]
    for run_id in ids:
        background_tasks.add_task(loop.resume, run_id)
    if ids:
        _invalidar_telar()
    return {"approved": len(ids), "ids": ids}


@router.post(
    "/runs/{run_id}/answer",
    response_model=RunResponse,
    summary="Responder pregunta del agente y reanudar",
)
async def answer_run(
    run_id: str,
    background_tasks: BackgroundTasks,
    body: AnswerRequest,
) -> RunResponse:
    """
    Entrega la respuesta del usuario a una pregunta pendiente del agente
    y reanuda la ejecución en background.
    """
    loop = _get_loop()
    store = _get_store()

    try:
        run = store.get(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if run.status != AgentStatus.PENDING_QUESTION:
        raise HTTPException(
            status_code=409,
            detail=f"El run no está en pending_question (status={run.status})",
        )

    # Aceptamos la respuesta de forma SÍNCRONA (inyecta la respuesta + run → running) y dejamos la
    # continuación del LLM para background. Así la respuesta ya NO devuelve el estado viejo
    # (pending_question) y la UI no vuelve a pintar la misma pregunta; hace polling al estado real.
    run = loop.accept_answer(run_id, body.answer)
    background_tasks.add_task(loop.execute_run, run_id)
    return RunResponse.from_run(run)


@router.post(
    "/runs/{run_id}/cancel",
    response_model=RunResponse,
    summary="Cancelar un run activo",
)
async def cancel_run(run_id: str) -> RunResponse:
    """Cancela un run que esté en running, pending_approval o pending_question."""
    store = _get_store()
    try:
        run = store.get(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    cancellable = {AgentStatus.RUNNING, AgentStatus.PENDING_APPROVAL, AgentStatus.PENDING_QUESTION}
    if run.status not in cancellable:
        raise HTTPException(
            status_code=409,
            detail=f"El run no se puede cancelar (status={run.status})",
        )

    run.cancel()
    store.save_run(run)
    _invalidar_telar()
    return RunResponse.from_run(run)


@router.get("/tools", summary="Catálogo de tools registradas")
async def list_tools() -> list[dict]:
    """Lista todas las tools disponibles para el agente con su descripción y parámetros."""
    return [
        {
            "name": t.name,
            "description": t.description,
            "category": t.category,
            "requires_approval": t.requires_approval,
        }
        for t in tool_registry.all()
    ]


@router.get("/memory", summary="Vista completa de la memoria operativa del agente")
async def agent_memory() -> dict:
    """Devuelve el estado actual de la memoria persistente del agente."""
    return get_memory().snapshot()
