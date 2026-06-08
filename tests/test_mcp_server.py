"""
Tests del servidor MCP (Skill A) — protocolo JSON-RPC + gate de aprobación.

Dos niveles:
  1. Lógica de protocolo pura (`handle_message`/`handle_payload`), sin red.
  2. Integración HTTP end-to-end vía TestClient sobre `/mcp` (transporte real ASGI).

El foco crítico es el GATE: ninguna tool con efecto externo (correo, calendario,
shell, control de escritorio) puede ejecutarse vía MCP sin aprobación humana.
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from loombit_operator import mcp_server as mcp
from loombit_operator.main import app
from loombit_operator.tools import ToolDefinition, ToolRegistry

# ── Registry de juguete para tests deterministas ───────────────────────────────


def _fake_registry() -> ToolRegistry:
    """Registry mínimo: una tool de lectura (echo) y una con efecto (requires_approval)."""
    reg = ToolRegistry()
    reg.register(
        ToolDefinition(
            name="echo",
            description="Devuelve el texto recibido.",
            parameters={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
            fn=lambda text: f"echo:{text}",
            category="base",
        )
    )

    def _boom() -> str:  # pragma: no cover - no debe ejecutarse nunca
        raise AssertionError("¡el gate falló: una tool con efecto se ejecutó!")

    reg.register(
        ToolDefinition(
            name="do_effect",
            description="Acción con efecto externo (no debe auto-ejecutarse).",
            parameters={"type": "object", "properties": {}},
            fn=_boom,
            requires_approval=True,
            safety_class="assisted",
            category="connector",
        )
    )
    return reg


def _req(method: str, params: dict | None = None, msg_id: int | str = 1) -> dict:
    msg = {"jsonrpc": "2.0", "id": msg_id, "method": method}
    if params is not None:
        msg["params"] = params
    return msg


# ── 1. initialize ──────────────────────────────────────────────────────────────


def test_initialize_returns_server_info_and_capabilities() -> None:
    resp = mcp.handle_message(_req("initialize", {"protocolVersion": "2025-06-18"}))
    assert resp is not None
    result = resp["result"]
    assert result["protocolVersion"] == "2025-06-18"
    assert result["serverInfo"]["name"] == mcp.SERVER_NAME
    assert "tools" in result["capabilities"]
    assert result["instructions"]


def test_initialize_negotiates_unsupported_version_down_to_default() -> None:
    resp = mcp.handle_message(_req("initialize", {"protocolVersion": "1999-01-01"}))
    assert resp["result"]["protocolVersion"] == mcp.DEFAULT_PROTOCOL_VERSION


# ── 2. tools/list ──────────────────────────────────────────────────────────────


def test_tools_list_reflects_registry_with_schema_and_meta() -> None:
    reg = _fake_registry()
    resp = mcp.handle_message(_req("tools/list"), reg)
    tools = {t["name"]: t for t in resp["result"]["tools"]}
    assert set(tools) == {"echo", "do_effect"}
    echo = tools["echo"]
    assert echo["inputSchema"]["properties"]["text"]["type"] == "string"
    assert echo["_meta"]["loombit"]["auto_executes_over_mcp"] is True
    assert echo["annotations"]["destructiveHint"] is False
    # La tool con efecto se anuncia como destructiva y NO auto-ejecutable.
    eff = tools["do_effect"]
    assert eff["annotations"]["destructiveHint"] is True
    assert eff["_meta"]["loombit"]["auto_executes_over_mcp"] is False


def test_tools_list_real_registry_count_matches() -> None:
    from loombit_operator.tools import tool_registry

    resp = mcp.handle_message(_req("tools/list"))
    assert len(resp["result"]["tools"]) == len(tool_registry.list())


# ── 3. tools/call: lectura ejecuta ─────────────────────────────────────────────


def test_tools_call_read_tool_executes() -> None:
    reg = _fake_registry()
    resp = mcp.handle_message(
        _req("tools/call", {"name": "echo", "arguments": {"text": "hola"}}), reg
    )
    result = resp["result"]
    assert result["isError"] is False
    assert result["content"][0]["text"] == "echo:hola"


# ── 4. GATE: efecto externo NO se ejecuta ──────────────────────────────────────


def test_gate_blocks_effectful_tool_without_executing_it() -> None:
    reg = _fake_registry()
    # Si el gate fallara, _boom() lanzaría AssertionError y el test caería con ese mensaje.
    resp = mcp.handle_message(_req("tools/call", {"name": "do_effect", "arguments": {}}), reg)
    result = resp["result"]
    assert result["isError"] is True
    payload = json.loads(result["content"][0]["text"])
    assert payload["status"] == "requires_human_approval"
    assert payload["tool"] == "do_effect"


def test_gate_covers_real_effectful_tools() -> None:
    """En el registry real: correo, calendario, shell y control de escritorio están gateados."""
    from loombit_operator.tools import tool_registry

    for name in ("gmail_send", "calendar_create", "run_shell", "desktop_click", "desktop_type"):
        tool = tool_registry.get(name)
        assert mcp.requires_human_approval(tool) is True, f"{name} debería estar gateada"


def test_read_tools_are_not_gated() -> None:
    from loombit_operator.tools import tool_registry

    for name in ("gmail_search", "contacts_find", "read_file", "list_directory"):
        tool = tool_registry.get(name)
        assert mcp.requires_human_approval(tool) is False, f"{name} no debería estar gateada"


# ── 5. errores y casos límite ──────────────────────────────────────────────────


def test_tools_call_unknown_tool_is_error_not_protocol_error() -> None:
    resp = mcp.handle_message(_req("tools/call", {"name": "no_existe", "arguments": {}}))
    assert "result" in resp
    assert resp["result"]["isError"] is True
    assert "desconocida" in resp["result"]["content"][0]["text"].lower()


def test_tools_call_missing_name_is_invalid_params() -> None:
    resp = mcp.handle_message(_req("tools/call", {"arguments": {}}))
    assert resp["error"]["code"] == mcp.INVALID_PARAMS


def test_unknown_method_returns_method_not_found() -> None:
    resp = mcp.handle_message(_req("does/not/exist"))
    assert resp["error"]["code"] == mcp.METHOD_NOT_FOUND


def test_ping_returns_empty_result() -> None:
    resp = mcp.handle_message(_req("ping"))
    assert resp["result"] == {}


def test_notification_returns_none() -> None:
    # Sin 'id' → notificación → no se responde.
    assert mcp.handle_message({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_invalid_jsonrpc_is_invalid_request() -> None:
    resp = mcp.handle_message({"method": "ping", "id": 1})  # falta jsonrpc
    assert resp["error"]["code"] == mcp.INVALID_REQUEST


# ── 6. batch ───────────────────────────────────────────────────────────────────


def test_batch_processes_each_and_skips_notifications() -> None:
    batch = [
        _req("ping", msg_id=1),
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        _req("ping", msg_id=2),
    ]
    out = mcp.handle_payload(batch)
    assert isinstance(out, list)
    assert [r["id"] for r in out] == [1, 2]


def test_batch_of_only_notifications_returns_none() -> None:
    batch = [{"jsonrpc": "2.0", "method": "notifications/initialized"}]
    assert mcp.handle_payload(batch) is None


def test_empty_batch_is_invalid_request() -> None:
    assert mcp.handle_payload([])["error"]["code"] == mcp.INVALID_REQUEST


# ── 7. Integración HTTP end-to-end (transporte Streamable HTTP) ─────────────────


def test_http_full_handshake() -> None:
    client = TestClient(app)

    # initialize
    r = client.post("/mcp", json=_req("initialize", {"protocolVersion": "2025-06-18"}))
    assert r.status_code == 200
    assert r.json()["result"]["serverInfo"]["name"] == mcp.SERVER_NAME

    # notifications/initialized → 202 sin cuerpo
    r = client.post("/mcp", json={"jsonrpc": "2.0", "method": "notifications/initialized"})
    assert r.status_code == 202

    # tools/list
    r = client.post("/mcp", json=_req("tools/list", msg_id=2))
    assert r.status_code == 200
    names = [t["name"] for t in r.json()["result"]["tools"]]
    assert "gmail_send" in names and "read_file" in names

    # tools/call de lectura (list_directory sobre un dir que existe)
    r = client.post(
        "/mcp",
        json=_req("tools/call", {"name": "list_directory", "arguments": {"path": "."}}, msg_id=3),
    )
    assert r.status_code == 200
    assert r.json()["result"]["isError"] is False


def test_http_gate_over_the_wire() -> None:
    client = TestClient(app)
    r = client.post(
        "/mcp",
        json=_req(
            "tools/call",
            {
                "name": "gmail_send",
                "arguments": {"to": "x@example.com", "subject": "s", "body": "b"},
            },
        ),
    )
    assert r.status_code == 200
    result = r.json()["result"]
    assert result["isError"] is True
    assert json.loads(result["content"][0]["text"])["status"] == "requires_human_approval"


def test_http_invalid_json_is_parse_error() -> None:
    client = TestClient(app)
    r = client.post("/mcp", content=b"{not json", headers={"content-type": "application/json"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == mcp.PARSE_ERROR


def test_http_get_not_allowed() -> None:
    client = TestClient(app)
    assert client.get("/mcp").status_code == 405


def test_http_info_lists_auto_vs_gated() -> None:
    client = TestClient(app)
    body = client.get("/mcp/info").json()
    assert "gmail_send" in body["requires_human_approval"]
    assert "gmail_search" in body["auto_executes"]
    assert body["tool_count"] >= 1
