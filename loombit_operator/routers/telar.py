"""
routers/telar.py — La tela de la mañana.

GET /telar → el día tejido en hilos accionables (`telar.tejer_dia`). Cada hilo trae su
acción preparada; la UI ejecuta los `agent_task` por el flujo del agente (POST /agent/run),
que aplica aprobación + firma + proactividad. Solo lectura aquí.
"""

from __future__ import annotations

from fastapi import APIRouter

from ..telar import tejer_dia

router = APIRouter(tags=["telar"])


@router.get("/telar")
def telar() -> dict:
    return tejer_dia()
