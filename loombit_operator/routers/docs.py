"""
Router de inteligencia documental — leer facturas y aprender de ellas.

POST /docs-intel/invoice
  Extrae los campos de una factura (de `text` o de un PDF en `path`), aplica el
  gate antifraude de IBAN contra la memoria de empresa, aprende el perfil del
  proveedor y, opcionalmente, cruza el total con el albarán.

Cumple los gates del dominio: nunca inventa datos, y un IBAN nuevo en un
proveedor conocido NO se registra (se marca para verificación humana).
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from loombit_operator.agent.memory import get_memory
from loombit_operator.docs_intel import (
    cross_check_amount,
    extract_invoice_fields,
    extract_text_from_pdf,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/docs-intel", tags=["docs-intel"])


class InvoiceRequest(BaseModel):
    text: str = ""
    path: str = ""
    learn: bool = True
    albaran_total: float | None = None


@router.post("/invoice")
async def read_invoice(body: InvoiceRequest) -> dict[str, Any]:
    text = body.text
    if not text and body.path:
        pdf_info = extract_text_from_pdf(body.path)
        if pdf_info.get("error"):
            raise HTTPException(status_code=400, detail=pdf_info["error"])
        text = pdf_info.get("text", "")
        if pdf_info.get("needs_ocr"):
            return {
                "result": "El PDF parece escaneado (sin texto). Falta visión local (Qwen2.5-VL) para leerlo.",
                "needs_ocr": True,
                "fields": None,
            }
    if not text:
        raise HTTPException(status_code=400, detail="Indica `text` o `path`.")

    inv = extract_invoice_fields(text)
    fields = inv.to_dict()
    entity_name = inv.proveedor or ""
    warnings: list[str] = []
    iban_verdict: dict[str, Any] | None = None
    learned = False

    # Gate antifraude de IBAN + aprendizaje de la empresa.
    if (inv.nif or entity_name) and inv.iban:
        mem = get_memory()
        iban_verdict = mem.iban_alert(name=entity_name, iban=inv.iban, nif=inv.nif or "")
        if iban_verdict["is_new_for_known_entity"]:
            warnings.append(
                "IBAN NUEVO para un proveedor conocido — posible fraude (BEC). "
                "No se registra: verifica por un canal alternativo antes de pagar."
            )
        if body.learn:
            # Aprende siempre la empresa; el IBAN solo si NO es sospechoso.
            iban_to_learn = "" if iban_verdict["is_new_for_known_entity"] else inv.iban
            mem.upsert_entity(
                name=entity_name or inv.nif, nif=inv.nif or "", iban=iban_to_learn or ""
            )
            learned = True
    elif body.learn and (inv.nif or entity_name):
        get_memory().upsert_entity(name=entity_name or inv.nif, nif=inv.nif or "")
        learned = True

    # Cruce con albarán (supuestos G / S-04).
    cross: dict[str, Any] | None = None
    if body.albaran_total is not None:
        cross = cross_check_amount(inv.total, body.albaran_total)
        if cross.get("comparable") and not cross.get("match"):
            warnings.append(
                f"El total ({inv.total}) no cuadra con el albarán ({body.albaran_total}); "
                "bloquear y solicitar factura rectificativa."
            )

    # Resumen humano.
    parts = [f"Factura {inv.numero or '¿?'}"]
    if inv.proveedor:
        parts.append(f"de {inv.proveedor}")
    if inv.total is not None:
        parts.append(f"por {inv.total:g} €")
    if inv.vencimiento:
        parts.append(f"(vence {inv.vencimiento})")
    result = " ".join(parts) + "."
    if inv.missing:
        result += f" Faltan datos fiables: {', '.join(inv.missing)}."
    for w in warnings:
        result += " ⚠ " + w

    return {
        "result": result,
        "fields": fields,
        "iban_check": iban_verdict,
        "cross_check": cross,
        "learned_entity": learned,
        "warnings": warnings,
    }
