"""
Skill A — MCP Server: expone el `tool_registry` de Loombit como servidor MCP.

El Model Context Protocol (MCP) es el estándar abierto para que clientes (Claude
Desktop, Cursor, el MCP Inspector, otros agentes…) descubran y llamen herramientas
de un servidor. Este módulo es un **adaptador puro** (Skill A, reemplazable): NO
contiene lógica de dominio; refleja lo que haya en el `tool_registry`. Si mañana
se cambia el registry, el servidor MCP cambia solo.

Transporte y wiring HTTP viven en `routers/mcp.py`; aquí está SOLO la lógica del
protocolo (JSON-RPC 2.0 + métodos MCP), para que sea testeable sin red.

── Gate de seguridad (regla nº 1 de Loombit: el operador NUNCA ejecuta un efecto
   externo sin aprobación humana) ──────────────────────────────────────────────
Un cliente MCP arbitrario no es de fiar para hacer el human-in-the-loop, así que
el gate vive en el servidor (defensa en profundidad): `tools/call` sobre una tool
que afecta al mundo (envío de correo, evento de calendario, shell, control de
escritorio) NO se ejecuta — se devuelve `isError` con "requiere aprobación
humana en Loombit" y la acción preparada. Las tools de lectura/preparación
(leer fichero, buscar correo, buscar contacto, fetch web) sí responden.

Estado: 🟡 — protocolo implementado y verificado end-to-end con TestClient; el
recibo 🟢 lo da un cliente MCP externo real (ver `routers/mcp.py` y el README).
"""

from __future__ import annotations

import json
from typing import Any

from .tools import ToolDefinition, tool_registry  # importa → puebla el registry

# ── Identidad del servidor y versiones de protocolo soportadas ─────────────────
SERVER_NAME = "loombit-operator"
SERVER_VERSION = "0.1.0"
# Versiones del protocolo MCP que sabemos hablar (de más nueva a más vieja).
SUPPORTED_PROTOCOL_VERSIONS: tuple[str, ...] = ("2025-06-18", "2025-03-26", "2024-11-05")
DEFAULT_PROTOCOL_VERSION = SUPPORTED_PROTOCOL_VERSIONS[0]

SERVER_INSTRUCTIONS = (
    "Loombit Operator expuesto como servidor MCP. Las herramientas de lectura y "
    "preparación se ejecutan al llamarlas. Las que producen un efecto externo "
    "(enviar correo, crear evento, ejecutar shell, controlar el escritorio) NO se "
    "ejecutan automáticamente: devuelven isError y la acción queda preparada a la "
    "espera de aprobación humana dentro de Loombit. El número/dinero lo calcula "
    "código determinista; el modelo solo narra."
)

# Categorías cuyo efecto recae sobre el mundo/equipo del usuario → nunca auto-exec.
# `pilot` y `computer` controlan ratón/teclado/pantalla del usuario (capturan su
# pantalla, mueven el cursor, teclean): exigen el consentimiento del Pilot, no se
# disparan desde un cliente MCP remoto. `shell` ejecuta comandos.
_EFFECTFUL_CATEGORIES: frozenset[str] = frozenset({"computer", "pilot", "shell"})
# Clases de seguridad que nunca se auto-ejecutan por MCP.
_SENSITIVE_SAFETY: frozenset[str] = frozenset({"safety_sensitive", "blocked_by_default"})
# Tools de solo-lectura conocidas (para el hint readOnlyHint, honesto).
_READ_ONLY_NAMES: frozenset[str] = frozenset(
    {"read_file", "list_directory", "web_fetch", "gmail_search", "contacts_find", "read_invoice"}
)

# Códigos de error JSON-RPC 2.0 estándar.
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


# ── Gate: ¿esta tool requiere aprobación humana (no auto-exec por MCP)? ─────────
def requires_human_approval(tool: ToolDefinition) -> bool:
    """True si la tool afecta al mundo externo y por tanto el servidor MCP NO debe
    ejecutarla sin aprobación humana dentro de Loombit."""
    return (
        tool.requires_approval
        or tool.category in _EFFECTFUL_CATEGORIES
        or tool.safety_class in _SENSITIVE_SAFETY
    )


def _negotiate_version(requested: Any) -> str:
    """Devuelve la versión pedida si la soportamos; si no, nuestra más reciente."""
    if isinstance(requested, str) and requested in SUPPORTED_PROTOCOL_VERSIONS:
        return requested
    return DEFAULT_PROTOCOL_VERSION


def _tool_to_mcp(tool: ToolDefinition) -> dict[str, Any]:
    """Convierte un `ToolDefinition` al descriptor de tool de MCP.

    El `inputSchema` de MCP es exactamente el JSON Schema de los parámetros. Las
    `annotations` son hints opcionales; la verdad autoritativa de Loombit
    (requires_approval, safety_class, autoexec) va en `_meta` para no perderla."""
    blocked = requires_human_approval(tool)
    return {
        "name": tool.name,
        "description": tool.description,
        "inputSchema": tool.parameters,
        "annotations": {
            "title": tool.name,
            "readOnlyHint": (not blocked) and tool.name in _READ_ONLY_NAMES,
            "destructiveHint": blocked,
        },
        "_meta": {
            "loombit": {
                "category": tool.category,
                "safety_class": tool.safety_class,
                "requires_approval": tool.requires_approval,
                "auto_executes_over_mcp": not blocked,
            }
        },
    }


# ── Envelopes JSON-RPC ─────────────────────────────────────────────────────────
def _ok(msg_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _err(msg_id: Any, code: int, message: str, data: Any = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": msg_id, "error": error}


def _text_content(text: str, is_error: bool = False) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


# ── Handlers por método ────────────────────────────────────────────────────────
def _handle_initialize(params: dict[str, Any]) -> dict[str, Any]:
    return {
        "protocolVersion": _negotiate_version(params.get("protocolVersion")),
        "capabilities": {"tools": {"listChanged": False}},
        "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        "instructions": SERVER_INSTRUCTIONS,
    }


def _handle_tools_list(registry: Any) -> dict[str, Any]:
    return {"tools": [_tool_to_mcp(t) for t in registry.list()]}


def _handle_tools_call(params: dict[str, Any], registry: Any) -> dict[str, Any]:
    """Ejecuta una tool respetando el gate. Devuelve un *result* MCP (con isError),
    nunca un error de protocolo: los fallos de la tool se reportan en el contenido."""
    name = params.get("name")
    arguments = params.get("arguments", {}) or {}
    if not isinstance(name, str) or not name:
        raise _ParamsError("Falta 'name' en tools/call")
    if not isinstance(arguments, dict):
        raise _ParamsError("'arguments' debe ser un objeto")

    try:
        tool = registry.get(name)
    except KeyError:
        return _text_content(f"Tool desconocida: '{name}'", is_error=True)

    # Gate: las tools con efecto externo no se ejecutan sin aprobación humana.
    if requires_human_approval(tool):
        gate = {
            "ok": False,
            "status": "requires_human_approval",
            "tool": name,
            "prepared_arguments": arguments,
            "reason": (
                "Loombit no ejecuta efectos externos sin aprobación humana. La acción "
                "queda PREPARADA; apruébala dentro de Loombit para ejecutarla."
            ),
            "safety_class": tool.safety_class,
        }
        return _text_content(json.dumps(gate, ensure_ascii=False), is_error=True)

    # Tool de lectura/preparación: ejecutar y envolver el resultado.
    try:
        result = tool.execute(**arguments)
    except TypeError as exc:  # argumentos que no casan con la firma
        return _text_content(f"Argumentos inválidos para '{name}': {exc}", is_error=True)
    except Exception as exc:  # noqa: BLE001 — el fallo se reporta, no tumba el servidor
        return _text_content(f"Error ejecutando '{name}': {exc}", is_error=True)

    text = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
    return _text_content(text, is_error=False)


class _ParamsError(Exception):
    """Parámetros inválidos → se traduce a JSON-RPC -32602."""


# ── Dispatch ───────────────────────────────────────────────────────────────────
def handle_message(message: Any, registry: Any | None = None) -> dict[str, Any] | None:
    """Procesa UN mensaje JSON-RPC. Devuelve la respuesta, o None si era una
    notificación (sin `id`, no se responde)."""
    reg = registry if registry is not None else tool_registry

    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        return _err(None, INVALID_REQUEST, "Mensaje JSON-RPC 2.0 inválido")

    method = message.get("method")
    msg_id = message.get("id")
    is_notification = "id" not in message
    params = message.get("params") or {}
    if not isinstance(params, dict):
        params = {}

    # Notificaciones: se procesan en silencio (no se responde nunca).
    if is_notification:
        return None

    if not isinstance(method, str):
        return _err(msg_id, INVALID_REQUEST, "Falta 'method'")

    try:
        if method == "initialize":
            return _ok(msg_id, _handle_initialize(params))
        if method == "ping":
            return _ok(msg_id, {})
        if method == "tools/list":
            return _ok(msg_id, _handle_tools_list(reg))
        if method == "tools/call":
            return _ok(msg_id, _handle_tools_call(params, reg))
        return _err(msg_id, METHOD_NOT_FOUND, f"Método no soportado: '{method}'")
    except _ParamsError as exc:
        return _err(msg_id, INVALID_PARAMS, str(exc))
    except Exception as exc:  # noqa: BLE001
        return _err(msg_id, INTERNAL_ERROR, f"Error interno: {exc}")


def handle_payload(
    payload: Any, registry: Any | None = None
) -> dict[str, Any] | list[dict[str, Any]] | None:
    """Procesa un mensaje suelto o un batch JSON-RPC (lista). Para un batch,
    devuelve la lista de respuestas (omitiendo las notificaciones); si todo eran
    notificaciones, devuelve None."""
    if isinstance(payload, list):
        if not payload:
            return _err(None, INVALID_REQUEST, "Batch vacío")
        responses = [r for r in (handle_message(m, registry) for m in payload) if r is not None]
        return responses or None
    return handle_message(payload, registry)
