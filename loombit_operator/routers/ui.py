"""
Sirve la interfaz web de Skill Skins desde loombit_operator/static/.

GET /        → index.html (home + chat)
GET /static/ → ficheros estáticos adicionales (css, js, imágenes futuras)
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

STATIC_DIR = Path(__file__).parent.parent / "static"

router = APIRouter(tags=["ui"])


@router.get("/", include_in_schema=False)
async def serve_home() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html", media_type="text/html")
