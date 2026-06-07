"""
Router de Computer Use — puente entre el AgentLoop y la extensión Chrome.

El AgentLoop llama a tools/computer.py que hace POST a /computer-use/*.
Este router recibe esas llamadas y las ejecuta via Claude-in-Chrome MCP.

Por ahora expone una API interna. En producción se añadirá autenticación
para que solo el propio proceso pueda llamarla.

Endpoints:
  POST /computer-use/navigate     — ir a URL
  POST /computer-use/click        — clic en selector o coordenadas
  POST /computer-use/type         — escribir texto
  POST /computer-use/key          — pulsar tecla
  POST /computer-use/scroll       — scroll
  POST /computer-use/screenshot   — captura de pantalla
  POST /computer-use/read_page    — leer texto de la página
  POST /computer-use/find         — buscar elemento
  GET  /computer-use/status       — estado de la conexión Chrome
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/computer-use", tags=["computer-use"])

# ── Modelos ───────────────────────────────────────────────────────────────────

class NavigateRequest(BaseModel):
    url: str

class ClickRequest(BaseModel):
    selector: str = ""
    x: int = 0
    y: int = 0

class TypeRequest(BaseModel):
    text: str

class KeyRequest(BaseModel):
    key: str

class ScrollRequest(BaseModel):
    direction: str = "down"
    amount: int = 3

class FindRequest(BaseModel):
    query: str


# ── Helper: Chrome MCP bridge ─────────────────────────────────────────────────
# Las funciones del MCP Claude-in-Chrome no están disponibles como funciones
# Python directas en el operador. El operador corre como proceso independiente.
#
# Estrategia de integración:
#   1. El router expone los endpoints
#   2. Para cada acción, llamamos al proceso Loombit que tiene acceso al MCP
#      a través de la variable de entorno LOOMBIT_CHROME_TAB_ID
#   3. Si no hay tab ID configurado → devuelve 503 (extensión no conectada)
#
# En la práctica, Fernando arrancará el operador desde Claude (Cowork mode)
# donde sí hay acceso al MCP. Cuando el operador corra standalone, las
# computer-use tools estarán en modo "stub" hasta que se conecte un adapter.

import os

_CHROME_TAB_ID: int | None = None

def get_tab_id() -> int | None:
    global _CHROME_TAB_ID
    if _CHROME_TAB_ID:
        return _CHROME_TAB_ID
    env_val = os.environ.get("LOOMBIT_CHROME_TAB_ID", "")
    if env_val.isdigit():
        _CHROME_TAB_ID = int(env_val)
    return _CHROME_TAB_ID

def chrome_unavailable():
    raise HTTPException(
        status_code=503,
        detail=(
            "Extensión Chrome no conectada. "
            "Configura LOOMBIT_CHROME_TAB_ID o arranca el operador desde Claude Cowork."
        ),
    )

# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/status")
async def computer_status() -> dict:
    tab_id = get_tab_id()
    return {
        "chrome_connected": tab_id is not None,
        "tab_id": tab_id,
        "note": "Configura LOOMBIT_CHROME_TAB_ID=<id> para activar computer use.",
    }

@router.post("/navigate")
async def navigate(body: NavigateRequest) -> dict:
    tab_id = get_tab_id()
    if tab_id is None:
        chrome_unavailable()
    # Stub: cuando el adapter real esté conectado, aquí irá la llamada MCP
    logger.info("computer-use navigate: %s (tab=%s)", body.url, tab_id)
    return {"result": f"[STUB] Navegando a {body.url} en tab {tab_id}"}

@router.post("/click")
async def click(body: ClickRequest) -> dict:
    tab_id = get_tab_id()
    if tab_id is None:
        chrome_unavailable()
    target = body.selector if body.selector else f"({body.x},{body.y})"
    logger.info("computer-use click: %s (tab=%s)", target, tab_id)
    return {"result": f"[STUB] Clic en {target}"}

@router.post("/type")
async def type_text(body: TypeRequest) -> dict:
    tab_id = get_tab_id()
    if tab_id is None:
        chrome_unavailable()
    logger.info("computer-use type: %d chars (tab=%s)", len(body.text), tab_id)
    return {"result": f"[STUB] Texto escrito ({len(body.text)} caracteres)"}

@router.post("/key")
async def press_key(body: KeyRequest) -> dict:
    tab_id = get_tab_id()
    if tab_id is None:
        chrome_unavailable()
    logger.info("computer-use key: %s (tab=%s)", body.key, tab_id)
    return {"result": f"[STUB] Tecla pulsada: {body.key}"}

@router.post("/scroll")
async def scroll(body: ScrollRequest) -> dict:
    tab_id = get_tab_id()
    if tab_id is None:
        chrome_unavailable()
    return {"result": f"[STUB] Scroll {body.direction} x{body.amount}"}

@router.post("/screenshot")
async def screenshot() -> dict:
    tab_id = get_tab_id()
    if tab_id is None:
        chrome_unavailable()
    return {"result": "[STUB] Captura no disponible — conecta la extensión Chrome."}

@router.post("/read_page")
async def read_page() -> dict:
    tab_id = get_tab_id()
    if tab_id is None:
        chrome_unavailable()
    return {"result": "[STUB] Lectura de página no disponible — conecta la extensión Chrome."}

@router.post("/find")
async def find(body: FindRequest) -> dict:
    tab_id = get_tab_id()
    if tab_id is None:
        chrome_unavailable()
    logger.info("computer-use find: %s (tab=%s)", body.query, tab_id)
    return {"result": f"[STUB] Buscando '{body.query}' — conecta la extensión Chrome."}
