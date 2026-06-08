"""
routers/galaxia.py — la Galaxia: el negocio como sistema estelar (`docs/GALAXIA_LOOMBIT.md`).

GET  /galaxia          → `{ sol, nodos[], aristas[], meta }` (pre-cargado: instantáneo +
                         revalidación en segundo plano, ver `galaxia_cache`). `?force=1` reconstruye.
GET  /galaxia/contacto → destila el contexto real de un contacto (lazy, al enfocar su planeta).
POST /galaxia/act      → drag-to-act: resuelve (qué arrastras × dónde sueltas) → acción. Los
                         efectos externos se enrutan al agente (aprobación + firma + proactividad).
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel, Field

from .. import galaxia_cache
from ..galaxia_actions import resolve_drop
from ..galaxia_intel import distill_contacto

router = APIRouter(tags=["galaxia"])


@router.get("/galaxia")
def galaxia(force: bool = False) -> dict:
    return galaxia_cache.get(force=force)


@router.get("/galaxia/contacto")
def galaxia_contacto(email: str, name: str = "", resumen: bool = True) -> dict:
    """Destila el contexto REAL de un contacto desde sus correos (lazy: al enfocar su planeta).
    Importes deterministas con procedencia; el LLM solo redacta el resumen de la relación."""
    return distill_contacto(email, name=name, use_llm=resumen).to_dict()


class DropRequest(BaseModel):
    source: dict = Field(
        default_factory=dict
    )  # lo que se arrastra (conversacion/documento/contacto)
    target: dict = Field(default_factory=dict)  # dónde se suelta (contacto/cuenta/sol)


@router.post("/galaxia/act")
def galaxia_act(body: DropRequest, background_tasks: BackgroundTasks) -> dict:
    """Resuelve un arrastre y, si la acción tiene efecto externo, la enruta al agente
    (que pausará para tu aprobación). Las acciones locales/navegación las resuelve la UI."""
    action = resolve_drop(body.source, body.target)
    out: dict = {"action": action.to_dict()}
    if action.modo == "agent_task" and action.task:
        from .agent import _get_loop

        loop = _get_loop()
        run = loop.create(task=action.task, profile="administrativo")
        background_tasks.add_task(loop.execute_run, run.id)
        out["run_id"] = run.id
    return out
