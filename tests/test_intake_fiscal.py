"""Tests del intake fiscal: factura extraída → línea de IVA → 303, con abstención honesta."""

from decimal import Decimal

from loombit_operator.docs_intel import InvoiceFields
from loombit_operator.expedientes import ExpedienteStatus, ExpedienteStore
from loombit_operator.skill_d_fiscal import (
    inferir_tipo_iva,
    linea_desde_factura,
    liquidar_303_periodo,
    registrar_factura,
)


def test_inferir_tipo_estandar():
    assert inferir_tipo_iva(1000, 210) == Decimal("0.21")
    assert inferir_tipo_iva(200, 20) == Decimal("0.10")
    assert inferir_tipo_iva(100, 4) == Decimal("0.04")


def test_inferir_tipo_no_estandar_o_invalido():
    assert inferir_tipo_iva(100, 5) is None  # 5% no es estándar
    assert inferir_tipo_iva(0, 0) is None  # base inválida


def test_linea_desde_factura_ok():
    inv = InvoiceFields(numero="F-1", base_imponible=1000.0, iva=210.0)
    linea, avisos = linea_desde_factura(inv, "devengado")
    assert avisos == []
    assert linea is not None
    assert linea.tipo == Decimal("0.21")
    assert linea.sentido == "devengado"


def test_linea_desde_factura_sin_datos_se_abstiene():
    inv = InvoiceFields(numero="F-2", base_imponible=None, iva=None)
    linea, avisos = linea_desde_factura(inv, "soportado")
    assert linea is None
    assert any("revisar manualmente" in a for a in avisos)


def test_linea_desde_factura_tipo_raro_se_abstiene():
    inv = InvoiceFields(numero="F-3", base_imponible=100.0, iva=5.2)  # recargo equiv.
    linea, avisos = linea_desde_factura(inv, "devengado")
    assert linea is None
    assert any("no estándar" in a for a in avisos)


def test_registrar_factura_crea_expediente(tmp_path):
    store = ExpedienteStore(entity_id="acme", base_dir=tmp_path)
    inv = InvoiceFields(numero="F-10", base_imponible=1000.0, iva=210.0, total=1210.0)
    exp = registrar_factura(store, inv, "devengado")
    assert exp.kind == "factura_intake"
    assert exp.data["sentido"] == "devengado"
    assert exp.data["fields"]["iva"] == 210.0
    assert store.verify_chain(exp.id) is True


def test_liquidar_303_periodo_end_to_end(tmp_path):
    store = ExpedienteStore(entity_id="acme", base_dir=tmp_path)
    # una emitida (devengado) y una recibida (soportado)
    registrar_factura(
        store, InvoiceFields(numero="E-1", base_imponible=1000.0, iva=210.0), "devengado"
    )
    registrar_factura(
        store, InvoiceFields(numero="R-1", base_imponible=500.0, iva=105.0), "soportado"
    )
    exp, res = liquidar_303_periodo(store, "2026-T2")
    assert exp.kind == "fiscal_303"
    assert exp.status == ExpedienteStatus.PENDING_APPROVAL  # la IA no presenta
    assert res.resultado == Decimal("105.00")  # 210 devengado - 105 deducible
    assert store.verify_chain(exp.id) is True


def test_liquidar_arrastra_avisos_de_facturas_ilegibles(tmp_path):
    store = ExpedienteStore(entity_id="acme", base_dir=tmp_path)
    registrar_factura(
        store, InvoiceFields(numero="OK", base_imponible=1000.0, iva=210.0), "devengado"
    )
    registrar_factura(
        store, InvoiceFields(numero="MALA", base_imponible=None, iva=None), "soportado"
    )
    exp, res = liquidar_303_periodo(store, "2026-T2")
    # la factura ilegible NO se inventa: aparece como aviso a revisar
    assert any("revisar manualmente" in a for a in res.avisos)
