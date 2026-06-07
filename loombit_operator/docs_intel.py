"""
docs_intel.py — inteligencia documental: extracción de campos de facturas (ES).

Convierte una factura (texto extraído de un PDF) en campos estructurados:
número, fecha, proveedor, NIF/CIF, base imponible, IVA, total, vencimiento, IBAN.

Reglas innegociables (gates del dominio):
  - NUNCA inventa un dato. Si un campo no se localiza con confianza, queda None y
    se lista en `missing` / `low_confidence`. Mejor "no lo sé" que un número falso.
  - Determinista y 100% local: sin nube, sin coste por llamada.

Para PDFs escaneados (sin capa de texto) el texto vendrá vacío; ahí el flujo debe
escalar a un modelo de visión local (Qwen2.5-VL) — pendiente.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Patrones (España) ─────────────────────────────────────────────────────────

# NIF (8 dígitos + letra), NIE (X/Y/Z + 7 dígitos + letra), CIF (letra + 7 díg + control)
_NIF_RE = re.compile(r"\b([A-HJ-NP-SUVW]\d{7}[0-9A-J]|[XYZ]\d{7}[A-Z]|\d{8}[A-Z])\b")
_IBAN_ES_RE = re.compile(r"\bES\d{2}(?:[ \-]?\d{4}){5}\b", re.IGNORECASE)
_DATE_RE = re.compile(r"\b(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}|\d{4}-\d{2}-\d{2})\b")
# Número de factura: admite F-2026/118, 2026/0042, FAC2026-001, etc.
_INVOICE_NO_RE = re.compile(
    r"(?:factura|n[ºo.]|num(?:ero)?)\s*[:#]?\s*([A-Z]{0,4}[-/]?\d{1,6}[-/]\d{1,6}|\d{2,8})",
    re.IGNORECASE,
)
_AMOUNT_TOKEN = r"\d{1,3}(?:[.\s]\d{3})*(?:,\d{1,2})?|\d+(?:,\d{1,2})?"


def parse_es_amount(raw: str) -> float | None:
    """
    Convierte un importe en formato español a float.
      "1.250"      -> 1250.0   ('.' separador de miles)
      "1.250,50"   -> 1250.5
      "4.800,00 €" -> 4800.0
      "968,00"     -> 968.0
    Devuelve None si no hay un número reconocible.
    """
    if not raw:
        return None
    m = re.search(_AMOUNT_TOKEN, raw)
    if not m:
        return None
    s = m.group(0).replace(" ", "")
    if "," in s:  # la coma es el decimal; los puntos son miles
        s = s.replace(".", "").replace(",", ".")
    else:
        # Solo puntos: si parecen miles (grupos de 3) se quitan; si no, es decimal.
        if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", s):
            s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


@dataclass
class InvoiceFields:
    numero: str | None = None
    fecha: str | None = None
    proveedor: str | None = None
    nif: str | None = None
    base_imponible: float | None = None
    iva: float | None = None
    total: float | None = None
    vencimiento: str | None = None
    iban: str | None = None
    low_confidence: list[str] = field(default_factory=list)

    @property
    def missing(self) -> list[str]:
        core = ("numero", "fecha", "nif", "total")
        return [k for k in core if getattr(self, k) in (None, "")]

    def to_dict(self) -> dict[str, Any]:
        return {
            "numero": self.numero,
            "fecha": self.fecha,
            "proveedor": self.proveedor,
            "nif": self.nif,
            "base_imponible": self.base_imponible,
            "iva": self.iva,
            "total": self.total,
            "vencimiento": self.vencimiento,
            "iban": self.iban,
            "missing": self.missing,
            "low_confidence": self.low_confidence,
        }


def _norm_iban(iban: str) -> str:
    return re.sub(r"[ \-]", "", iban).upper()


def _amount_after_keyword(text: str, keywords: list[str]) -> tuple[float | None, bool]:
    """Busca un importe en la misma línea que cualquiera de las palabras clave.
    Devuelve (valor, low_confidence)."""
    for line in text.splitlines():
        low = line.lower()
        if any(k in low for k in keywords):
            # toma el último número de la línea (suele ser el importe)
            nums = re.findall(_AMOUNT_TOKEN, line)
            if nums:
                val = parse_es_amount(nums[-1])
                if val is not None:
                    return val, False
    return None, True


def _date_after_keyword(text: str, keywords: list[str]) -> str | None:
    for line in text.splitlines():
        low = line.lower()
        if any(k in low for k in keywords):
            m = _DATE_RE.search(line)
            if m:
                return m.group(1)
    return None


def extract_invoice_fields(text: str) -> InvoiceFields:
    """Extrae los campos de una factura a partir de su texto. No inventa nada."""
    inv = InvoiceFields()
    if not text or not text.strip():
        inv.low_confidence = ["__sin_texto__"]
        return inv

    # NIF / CIF (el primero que aparece suele ser el del emisor)
    m = _NIF_RE.search(text)
    if m:
        inv.nif = m.group(1).upper()

    # IBAN
    m = _IBAN_ES_RE.search(text)
    if m:
        inv.iban = _norm_iban(m.group(0))

    # Número de factura
    m = _INVOICE_NO_RE.search(text)
    if m:
        inv.numero = m.group(1)
    else:
        inv.low_confidence.append("numero")

    # Fechas: emisión y vencimiento
    inv.vencimiento = _date_after_keyword(text, ["vencimiento", "vence", "fecha límite"])
    inv.fecha = _date_after_keyword(
        text, ["fecha de factura", "fecha factura", "fecha emisión", "fecha"]
    )
    if not inv.fecha:
        m = _DATE_RE.search(text)  # primera fecha del documento como respaldo
        if m:
            inv.fecha = m.group(1)
            inv.low_confidence.append("fecha")

    # Importes
    inv.total, lc_total = _amount_after_keyword(text, ["total a pagar", "total factura", "total"])
    if lc_total:
        inv.low_confidence.append("total")
    inv.base_imponible, lc_base = _amount_after_keyword(text, ["base imponible", "base"])
    if lc_base:
        inv.low_confidence.append("base_imponible")
    inv.iva, lc_iva = _amount_after_keyword(text, ["iva", "i.v.a"])
    if lc_iva:
        inv.low_confidence.append("iva")

    # Proveedor: primera línea no vacía (heurística débil → baja confianza)
    for line in text.splitlines():
        if line.strip():
            inv.proveedor = line.strip()[:80]
            break
    inv.low_confidence.append("proveedor")

    return inv


def cross_check_amount(
    invoice_total: float | None, reference_total: float | None, *, tolerance: float = 0.01
) -> dict[str, Any]:
    """
    Cruza el total de una factura con un importe de referencia (p. ej. el albarán).
    Supuesto G / S-04: si no cuadran, hay que bloquear y pedir rectificación.
    """
    if invoice_total is None or reference_total is None:
        return {"comparable": False, "match": False, "reason": "falta un importe"}
    diff = round(invoice_total - reference_total, 2)
    match = abs(diff) <= tolerance
    return {
        "comparable": True,
        "match": match,
        "invoice_total": invoice_total,
        "reference_total": reference_total,
        "difference": diff,
        "action": "ok" if match else "bloquear_y_solicitar_rectificacion",
    }


def extract_text_from_pdf(path: str | Path) -> dict[str, Any]:
    """
    Extrae la capa de texto de un PDF con pypdf. Si el PDF es escaneado (sin
    texto), `text` viene vacío y `needs_ocr=True` para escalar a visión local.
    """
    p = Path(path)
    if not p.exists():
        return {"text": "", "error": f"no existe: {p}", "needs_ocr": False}
    try:
        from pypdf import PdfReader
    except ImportError:
        return {"text": "", "error": "pypdf no instalado", "needs_ocr": False}
    try:
        reader = PdfReader(str(p))
        parts = [(page.extract_text() or "") for page in reader.pages]
        text = "\n".join(parts).strip()
        return {
            "text": text,
            "pages": len(reader.pages),
            "needs_ocr": not text,  # sin texto → probablemente escaneado
        }
    except Exception as exc:
        return {"text": "", "error": str(exc), "needs_ocr": False}
