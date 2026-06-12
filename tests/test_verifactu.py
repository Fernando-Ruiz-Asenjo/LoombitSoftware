"""
Arranque VeriFactu (factura → registro conforme encadenado) — golden con dientes. Determinista.
"""

from __future__ import annotations

from loombit_operator.docs_intel import InvoiceFields
from loombit_operator.skill_d_fiscal.verifactu import (
    GENESIS,
    encadenar,
    huella_registro,
    registro_desde_factura,
    verificar_cadena,
)

NIF = "B12345678"


def _inv(numero, total=1210.0, fecha="2026-05-10"):
    return InvoiceFields(numero=numero, fecha=fecha, total=total, nif=NIF)


# ── Registro conforme + cifras por código ─────────────────────────────────────


def test_registro_desde_factura_legible():
    reg, avisos = registro_desde_factura(_inv("F-2026-001"), NIF)
    assert reg is not None and avisos == []
    assert reg.importe_total == 1210.0  # cifra exacta de la factura, no estimada
    assert reg.huella and reg.huella_anterior == GENESIS


def test_abstencion_si_faltan_campos():
    reg, avisos = registro_desde_factura(_inv("F-1", total=None), NIF)
    assert reg is None and avisos and "no se registra" in avisos[0]


# ── Encadenamiento (inalterabilidad) ──────────────────────────────────────────


def test_encadenar_referencia_la_huella_anterior():
    regs, avisos = encadenar([_inv("F-1"), _inv("F-2")], NIF)
    assert len(regs) == 2 and avisos == []
    assert regs[1].huella_anterior == regs[0].huella  # encadenado
    assert verificar_cadena(regs) == []


def test_alterar_un_registro_rompe_la_cadena():
    regs, _ = encadenar([_inv("F-1"), _inv("F-2")], NIF)
    regs[0].importe_total = 9999.0  # alterar sin recomputar huella
    errores = verificar_cadena(regs)
    assert errores and any("huella no cuadra" in e for e in errores)


def test_reordenar_rompe_la_cadena():
    regs, _ = encadenar([_inv("F-1"), _inv("F-2"), _inv("F-3")], NIF)
    regs[1], regs[2] = regs[2], regs[1]
    assert verificar_cadena(regs)


def test_huella_es_determinista():
    reg, _ = registro_desde_factura(_inv("F-1"), NIF)
    assert reg.huella == huella_registro(reg)
