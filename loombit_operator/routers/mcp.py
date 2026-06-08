"""
Router del servidor MCP (transporte Streamable HTTP).

Expone Loombit como servidor MCP en un único endpoint POST `/mcp` que habla
JSON-RPC 2.0. La lógica del protocolo vive en `loombit_operator.mcp_server`
(puro/testeable); aquí solo está el wiring HTTP. Stateless: sin sesiones ni
stream servidor→cliente (no declaramos esa capacidad), así que GET → 405.

Clientes compatibles: Claude Desktop, Cursor, el MCP Inspector
(`npx @modelcontextprotocol/inspector`), o cualquier cliente que hable
Streamable HTTP.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from ..mcp_server import (
    PARSE_ERROR,
    SERVER_NAME,
    SERVER_VERSION,
    SUPPORTED_PROTOCOL_VERSIONS,
    _err,
    handle_payload,
    requires_human_approval,
)
from ..tools import tool_registry

router = APIRouter(tags=["mcp"])


@router.post("/mcp")
async def mcp_endpoint(request: Request) -> Response:
    """Endpoint JSON-RPC del servidor MCP.

    - Cuerpo JSON inválido → error de protocolo -32700.
    - Solo notificaciones (sin respuesta) → 202 Accepted, cuerpo vacío.
    - Resto → 200 con la respuesta (objeto o batch) JSON-RPC.
    """
    raw = await request.body()
    try:
        payload = json.loads(raw) if raw else None
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JSONResponse(_err(None, PARSE_ERROR, "JSON inválido"), status_code=400)

    if payload is None:
        return JSONResponse(_err(None, PARSE_ERROR, "Cuerpo vacío"), status_code=400)

    result = handle_payload(payload, tool_registry)
    if result is None:
        # Eran solo notificaciones: el protocolo no espera respuesta.
        return Response(status_code=202)
    return JSONResponse(result)


@router.get("/mcp")
def mcp_get() -> Response:
    """No ofrecemos stream servidor→cliente (SSE). El transporte es POST-only."""
    return JSONResponse(
        _err(None, -32600, "GET no soportado; usa POST con JSON-RPC 2.0"),
        status_code=405,
    )


@router.get("/mcp/info")
def mcp_info() -> dict:
    """Resumen humano (solo lectura) del servidor: identidad, versiones y qué
    herramientas se auto-ejecutan vs. cuáles exigen aprobación humana."""
    tools = tool_registry.list()
    auto = sorted(t.name for t in tools if not requires_human_approval(t))
    gated = sorted(t.name for t in tools if requires_human_approval(t))
    return {
        "server": {"name": SERVER_NAME, "version": SERVER_VERSION},
        "protocol_versions": list(SUPPORTED_PROTOCOL_VERSIONS),
        "transport": "streamable-http (POST /mcp)",
        "tool_count": len(tools),
        "auto_executes": auto,
        "requires_human_approval": gated,
    }
