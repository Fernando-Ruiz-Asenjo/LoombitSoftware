"""
Smoke test / recibo del servidor MCP de Loombit con un cliente MCP real (TCP).

Hace el handshake Streamable HTTP completo contra un Loombit en marcha y verifica
las cuatro propiedades que importan, guardando un recibo auditable:

  1. handshake (initialize → serverInfo == loombit-operator)
  2. tools/list devuelve el catálogo del registry
  3. una tool de LECTURA (list_directory) se ejecuta de verdad
  4. una tool con EFECTO externo (gmail_send) queda BLOQUEADA (requires_human_approval)

Uso:
    # 1) arranca Loombit (en otro terminal), p.ej. en un puerto aislado:
    python -m uvicorn loombit_operator.main:app --port 8799
    # 2) lanza el probe:
    python scripts/mcp_probe.py                 # usa http://127.0.0.1:8799/mcp
    python scripts/mcp_probe.py http://127.0.0.1:8787/mcp

Cliente alternativo (independiente, oficial), si tienes Node:
    npx @modelcontextprotocol/inspector --cli http://127.0.0.1:8799/mcp \
        --transport http --method tools/list
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx

DEFAULT_URL = "http://127.0.0.1:8799/mcp"
HEADERS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}


def _rpc(client: httpx.Client, url: str, method: str, params: dict | None = None, msg_id: int = 1):
    msg: dict = {"jsonrpc": "2.0", "id": msg_id, "method": method}
    if params is not None:
        msg["params"] = params
    return client.post(url, json=msg, headers=HEADERS).json()


def main(argv: list[str]) -> int:
    url = argv[1] if len(argv) > 1 else DEFAULT_URL
    with httpx.Client(timeout=15) as c:
        init = _rpc(
            c,
            url,
            "initialize",
            {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "probe"}},
            1,
        )
        c.post(url, json={"jsonrpc": "2.0", "method": "notifications/initialized"}, headers=HEADERS)
        tools = _rpc(c, url, "tools/list", {}, 2)["result"]["tools"]
        read = _rpc(c, url, "tools/call", {"name": "list_directory", "arguments": {"path": "."}}, 3)
        gated = _rpc(
            c,
            url,
            "tools/call",
            {
                "name": "gmail_send",
                "arguments": {"to": "x@example.com", "subject": "s", "body": "b"},
            },
            4,
        )

    gate_payload = json.loads(gated["result"]["content"][0]["text"])
    verdict = {
        "handshake_ok": init["result"]["serverInfo"]["name"] == "loombit-operator",
        "protocol": init["result"]["protocolVersion"],
        "tools_listed": len(tools),
        "read_tool_executed": read["result"]["isError"] is False,
        "effectful_tool_blocked": gated["result"]["isError"] is True
        and gate_payload.get("status") == "requires_human_approval",
    }
    ok = all(
        [
            verdict["handshake_ok"],
            verdict["tools_listed"] > 0,
            verdict["read_tool_executed"],
            verdict["effectful_tool_blocked"],
        ]
    )

    receipt_dir = Path("runtime/local/mcp_server")
    receipt_dir.mkdir(parents=True, exist_ok=True)
    receipt = {
        "what": "Recibo de protocolo del servidor MCP de Loombit",
        "url": url,
        "client": "scripts/mcp_probe.py (httpx, TCP real, Streamable HTTP)",
        "timestamp": datetime.now(UTC).isoformat(),
        "server_info": init["result"]["serverInfo"],
        "verdict": verdict,
        "ok": ok,
    }
    (receipt_dir / "receipt_protocol.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(json.dumps(verdict, ensure_ascii=False, indent=2))
    print("OK" if ok else "FALLÓ")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
