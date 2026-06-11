"""
routers/routines.py — API de Routines (agentes proactivos programados).

Endpoints:
- GET  /routines            → lista de rutinas (seedea el Brief diario si está vacío)
- POST /routines/tick       → dispara las rutinas que toquen ahora (cron)
- POST /routines/{id}/run   → fuerza una rutina ahora (demo/manual, ignora el cron)

El ejecutor real usa el LLM instructor (14B). Ver `docs/ROUTINES_LOOMBIT.md`.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..routine_executors import brief_executor, ensure_default_routines
from ..routines import RoutineNotFoundError, RoutineStore
from ..scheduler import RoutineScheduler

router = APIRouter(prefix="/routines", tags=["routines"])


class AprenderBody(BaseModel):
    texto: str


_EMPTY_WATCH = "Sin respuestas nuevas"


def _store() -> RoutineStore:
    return ensure_default_routines(RoutineStore())


def build_feed(receipt_dir: Path, limit: int = 30) -> list[dict]:
    """Lee los recibos del daemon (más recientes primero) y devuelve las NOVEDADES: descarta los
    ticks vacíos de vigilancia (ruido) y marca lo importante. Es lo que pinta el panel de la UI."""
    try:
        files = sorted(receipt_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    except Exception:
        return []
    items: list[dict] = []
    for f in files[: limit * 5]:
        try:
            j = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        out = j.get("output") or ""
        kind = j.get("output_kind", "")
        if kind == "reply_watch" and _EMPTY_WATCH in out:
            continue  # tick sin novedad → no es noticia
        items.append(
            {
                "name": j.get("name", ""),
                "kind": kind,
                "status": j.get("status", ""),
                "fired_at": j.get("fired_at", ""),
                "importante": ("[IMPORTANTE]" in out) or ("⚠ IMPORTANTE" in out),
                "output": out[:1500],
                "error": j.get("error", ""),
            }
        )
        if len(items) >= limit:
            break
    return items


@router.get("/feed")
def feed(limit: int = 30) -> dict:
    """Novedades/tareas detectadas por el daemon, para el panel de la UI."""
    from ..config import get_settings

    items = build_feed(get_settings().routine_receipt_dir, limit)
    return {"count": len(items), "items": items}


@router.get("/status")
def status(request: Request) -> dict:
    """Estado del agente proactivo para la UI ('Loombit está trabajando…'): latido del daemon
    + inventario de routines + recuento de novedades detectadas. Honesto: si el daemon está
    apagado (opt-in), dice 'en reposo', no finge actividad."""
    from ..config import get_settings

    daemon = getattr(request.app.state, "daemon", None)
    daemon_status = (
        daemon.status()
        if daemon is not None
        else {"running": False, "reason": "daemon apagado (opt-in en config)"}
    )
    routines = [
        {
            "name": r.name,
            "cron": r.schedule.expr,
            "tz": r.schedule.tz,
            "enabled": r.enabled,
            "safety": r.safety.value,
            "output_kind": r.output_kind,
            "last_fired": r.last_fired,
        }
        for r in _store().list()
    ]
    novedades = len(build_feed(get_settings().routine_receipt_dir, limit=30))
    trabajando = bool(daemon_status.get("running"))
    return {
        "trabajando": trabajando,
        "mensaje": (
            "Loombit está trabajando en segundo plano…"
            if trabajando
            else "Loombit en reposo (daemon apagado)."
        ),
        "daemon": daemon_status,
        "routines": routines,
        "novedades": novedades,
    }


@router.post("/aprender")
def aprender(body: AprenderBody) -> dict:
    """'Enséñale' (S2): de una orden en lenguaje natural a una skill/routine auto-disparada.
    El horario lo dispone el código (determinista); el efecto externo se queda en aprobación."""
    from ..aprender_skill import crear_skill_desde_texto

    try:
        return crear_skill_desde_texto(body.texto, _store())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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
