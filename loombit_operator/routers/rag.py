"""
routers/rag.py — API del índice semántico local (RAG, P1).

- POST /rag/reindexar        → (re)indexa el histórico real (ejecuciones, lecciones, empresas…)
- GET  /rag/buscar?q=&k=     → busca por SIGNIFICADO (no por palabra exacta), con score y procedencia
- GET  /rag/estado           → tamaño del índice, dimensión y desglose por fuente

Local-first: los vectores nunca salen de la máquina. Necesita el modelo de embeddings en LM Studio.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/reindexar")
def reindexar() -> dict[str, Any]:
    """Vectoriza e indexa el histórico real de la memoria operativa. Idempotente (dedup por id)."""
    from ..rag import get_index

    try:
        return get_index().reindexar_memoria()
    except Exception as exc:  # noqa: BLE001 — sin modelo de embeddings, informa con honestidad
        raise HTTPException(status_code=502, detail=f"no se pudo indexar: {exc}") from exc


@router.get("/buscar")
def buscar(q: str, k: int = 5, fuente: str | None = None) -> dict[str, Any]:
    """Búsqueda semántica: top-k por similitud de significado. `fuente` filtra (history/lesson/…)."""
    from ..rag import get_index

    try:
        resultados = get_index().search(q, k=k, fuente=fuente)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"no se pudo buscar: {exc}") from exc
    return {"query": q, "count": len(resultados), "resultados": resultados}


@router.get("/estado")
def estado() -> dict[str, Any]:
    """Estado del índice (sin tocar el modelo): tamaño, dimensión y desglose por fuente."""
    from ..rag import get_index

    return get_index().stats()
