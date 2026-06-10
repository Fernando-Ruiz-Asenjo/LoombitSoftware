"""
Tests del extractor de facturas españolas (docs_intel).

Clave: nunca inventa datos — los campos no localizados quedan None y en `missing`.
"""

from loombit_operator.docs_intel import (
    InvoiceFields,
    cross_check_amount,
    extract_invoice_fields,
    parse_es_amount,
)

SAMPLE_INVOICE = """\
Suministros Norte S.L.
CIF: B12345678
Factura Nº: 2026/0042
Fecha de factura: 15/05/2026
Vencimiento: 14/06/2026

Concepto                      Importe
Material de oficina           4.000,00

Base imponible                4.000,00
IVA (21%)                       840,00
Total a pagar                 4.840,00 €

Pago por transferencia a IBAN: ES12 3456 7890 1234 5678 9012
"""


# ── parse_es_amount ─────────────────────────────────────────────────────────


def test_parse_es_amount_formats():
    assert parse_es_amount("1.250") == 1250.0
    assert parse_es_amount("1.250,50") == 1250.5
    assert parse_es_amount("4.840,00 €") == 4840.0
    assert parse_es_amount("968,00") == 968.0
    assert parse_es_amount("12") == 12.0
    assert parse_es_amount("sin numero") is None


# ── extract_invoice_fields ──────────────────────────────────────────────────


def test_extract_full_invoice():
    inv = extract_invoice_fields(SAMPLE_INVOICE)
    assert inv.nif == "B12345678"
    assert inv.numero == "2026/0042"
    assert inv.fecha == "15/05/2026"
    assert inv.vencimiento == "14/06/2026"
    assert inv.total == 4840.0
    assert inv.base_imponible == 4000.0
    assert inv.iva == 840.0
    assert inv.iban == "ES1234567890123456789012"
    assert inv.missing == []  # numero, fecha, nif, total presentes


def test_extract_never_invents_on_empty():
    inv = extract_invoice_fields("")
    assert inv.numero is None
    assert inv.total is None
    assert "numero" in inv.missing and "total" in inv.missing


def test_extract_marks_missing_total():
    text = "Factura Nº: 7\nFecha: 01/01/2026\nCIF: B00000000\n(sin importe)"
    inv = extract_invoice_fields(text)
    assert inv.total is None
    assert "total" in inv.missing
    assert "total" in inv.low_confidence


def test_iban_checksum_invalido_marca_low_confidence():
    # IBAN con formato correcto pero checksum (mod-97) MANIPULADO → lectura dudosa (typo/OCR).
    malo = extract_invoice_fields("Factura Nº 9. IBAN: ES9121000418450200051333. Total: 100,00 €")
    bueno = extract_invoice_fields("Factura Nº 9. IBAN: ES9121000418450200051332. Total: 100,00 €")
    assert "iban" in malo.low_confidence  # checksum malo → se marca para verificar
    assert "iban" not in bueno.low_confidence  # checksum válido → no se marca


def test_invoice_roundtrip_dict():
    inv = InvoiceFields(numero="1", total=10.0)
    d = inv.to_dict()
    assert d["numero"] == "1"
    assert "missing" in d and "low_confidence" in d


# ── cross_check_amount (Supuesto G / S-04) ──────────────────────────────────


def test_cross_check_match():
    r = cross_check_amount(2100.0, 2100.0)
    assert r["match"] is True
    assert r["action"] == "ok"


def test_cross_check_mismatch_blocks():
    r = cross_check_amount(2340.0, 2100.0)
    assert r["match"] is False
    assert r["difference"] == 240.0
    assert r["action"] == "bloquear_y_solicitar_rectificacion"


def test_cross_check_incomparable():
    r = cross_check_amount(None, 100.0)
    assert r["comparable"] is False
