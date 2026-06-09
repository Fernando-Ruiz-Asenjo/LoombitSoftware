"""
routers/entregable.py — descarga del **entregable autónomo** de un expediente.

- GET  /entregable/{entity_id}/{expediente_id}        → dossier HTML autónomo (descarga por defecto;
                                                         `?descargar=false` para verlo inline).
- POST /entregable/{entity_id}/{expediente_id}/export → lo persiste en disco + recibo auditable.

Solo lectura sobre el expediente (salvo el export, que añade un evento `entregable_exportado`).
El HTML resultante es autocontenido: el cliente se lo queda y lo abre sin Loombit ni conexión.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from ..entregable import build_dossier, export_dossier
from ..expedientes import ExpedienteNotFoundError, ExpedienteStore

router = APIRouter(prefix="/entregable", tags=["entregable"])


@router.get("/{entity_id}/{expediente_id}")
def descargar_dossier(entity_id: str, expediente_id: str, descargar: bool = True) -> HTMLResponse:
    """Devuelve el dossier HTML autónomo del expediente. `descargar=true` fuerza la descarga."""
    try:
        store = ExpedienteStore(entity_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        html = build_dossier(store, expediente_id)
    except ExpedienteNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"expediente no encontrado: {exc}") from exc
    headers = {}
    if descargar:
        headers["Content-Disposition"] = f'attachment; filename="dossier_{expediente_id}.html"'
    return HTMLResponse(content=html, headers=headers)


@router.post("/{entity_id}/{expediente_id}/export")
def exportar_dossier(entity_id: str, expediente_id: str) -> dict[str, Any]:
    """Persiste el dossier en el disco de la entidad y deja un recibo auditable."""
    try:
        store = ExpedienteStore(entity_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        path = export_dossier(store, expediente_id)
    except ExpedienteNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"expediente no encontrado: {exc}") from exc
    return {"ok": True, "path": str(path), "recibo": str(path.with_suffix(".recibo.json"))}
