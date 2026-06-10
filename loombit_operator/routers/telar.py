"""
routers/telar.py — La tela de la mañana.

GET /telar → el día tejido en hilos accionables (`telar.tejer_dia`). Cada hilo trae su
acción preparada; la UI ejecuta los `agent_task` por el flujo del agente (POST /agent/run),
que aplica aprobación + firma + proactividad. Solo lectura aquí.
"""

from __future__ import annotations

from fastapi import APIRouter

from ..telar_cache import get_telar

router = APIRouter(tags=["telar"])


@router.get("/telar")
def telar() -> dict:
    # Servido al instante desde caché + refresco en 2º plano (auditoría UX P0-3). El cómputo real
    # (con sus llamadas a Google) vive en `telar.tejer_dia`; aquí solo se sirve cacheado.
    return get_telar()
