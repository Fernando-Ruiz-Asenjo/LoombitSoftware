"""Tool de inteligencia documental — el agente lee facturas (vía /docs-intel)."""

from __future__ import annotations

import json
import os

import httpx

from .registry import ToolDefinition, tool_registry

_BASE = os.environ.get("LOOMBIT_OPERATOR_URL", "http://127.0.0.1:8787")
_TIMEOUT = 30


def _read_invoice(path: str = "", text: str = "", albaran_total: float | None = None) -> str:
    payload: dict = {"learn": True}
    if path:
        payload["path"] = path
    if text:
        payload["text"] = text
    if albaran_total is not None:
        payload["albaran_total"] = albaran_total
    try:
        r = httpx.post(f"{_BASE}/docs-intel/invoice", json=payload, timeout=_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        return data.get("result", json.dumps(data, ensure_ascii=False))
    except Exception as exc:
        return f"ERROR: {exc}"


tool_registry.register(
    ToolDefinition(
        name="read_invoice",
        description=(
            "Lee una factura (PDF en `path` o texto en `text`) y extrae numero, fecha, "
            "NIF, base, IVA, total, vencimiento e IBAN. Aprende el proveedor en memoria y "
            "AVISA si el IBAN es nuevo para un proveedor conocido (posible fraude). Si pasas "
            "`albaran_total`, cruza el total y avisa si no cuadra. NUNCA inventa datos."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "default": ""},
                "text": {"type": "string", "default": ""},
                "albaran_total": {"type": "number"},
            },
        },
        fn=_read_invoice,
        category="docs",
    )
)
