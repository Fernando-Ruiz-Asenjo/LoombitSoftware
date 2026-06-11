"""Tests del Skill D Fiscal — cálculo determinista del 303 + integración con Expediente."""

# golden-source: Ley 37/1992 del IVA, arts. 90-91 (tipos 21/10/4) — las cuotas esperadas son base × tipo legal, calculadas de la ley, no del código.


from decimal import Decimal

from loombit_operator.expedientes import ExpedienteStatus, ExpedienteStore
from loombit_operator.skill_d_fiscal import (
    LineaIVA,
    borrador_303_texto,
    calcular_303,
    procesar_303,
)


def test_devengado_simple():
    res = calcular_303([LineaIVA(base=1000, tipo=0.21, sentido="devengado")])
    assert res.iva_devengado == Decimal("210.00")
    assert res.iva_deducible == Decimal("0.00")
    assert res.resultado == Decimal("210.00")
    assert res.a_ingresar is True


def test_devengado_menos_deducible():
    res = calcular_303(
        [
            LineaIVA(base=1000, tipo=0.21, sentido="devengado"),
            LineaIVA(base=500, tipo=0.21, sentido="soportado", deducible=True),
        ]
    )
    assert res.iva_devengado == Decimal("210.00")
    assert res.iva_deducible == Decimal("105.00")
    assert res.resultado == Decimal("105.00")


def test_resultado_a_compensar():
    res = calcular_303(
        [
            LineaIVA(base=100, tipo=0.21, sentido="devengado"),
            LineaIVA(base=1000, tipo=0.21, sentido="soportado"),
        ]
    )
    assert res.resultado == Decimal("-189.00")
    assert res.a_ingresar is False


def test_redondeo_half_up():
    # 33.33 * 0.21 = 6.9993 -> 7.00
    res = calcular_303([LineaIVA(base="33.33", tipo="0.21", sentido="devengado")])
    assert res.iva_devengado == Decimal("7.00")


def test_aviso_discrepancia_de_cuota():
    res = calcular_303(
        [LineaIVA(base=1000, tipo=0.21, sentido="devengado", cuota=200, concepto="Factura A")]
    )
    assert any("Discrepancia de cuota" in a for a in res.avisos)


def test_soportado_no_deducible_excluido():
    res = calcular_303(
        [LineaIVA(base=500, tipo=0.21, sentido="soportado", deducible=False, concepto="Comida")]
    )
    assert res.iva_deducible == Decimal("0.00")
    assert any("NO deducible" in a for a in res.avisos)


def test_regimen_no_general_avisa():
    res = calcular_303([LineaIVA(base=100, tipo=0.21, sentido="devengado")], regimen="caja")
    assert any("requiere revisión del asesor" in a for a in res.avisos)


def test_tipo_no_estandar_avisa():
    res = calcular_303([LineaIVA(base=100, tipo=0.052, sentido="devengado", concepto="Recargo")])
    assert any("Tipo de IVA no estándar" in a for a in res.avisos)


def test_casillas_principales():
    res = calcular_303(
        [
            LineaIVA(base=1000, tipo=0.21, sentido="devengado"),
            LineaIVA(base=200, tipo=0.10, sentido="devengado"),
            LineaIVA(base=300, tipo=0.21, sentido="soportado"),
        ]
    )
    assert res.casillas["01"] == "1000.00"  # base 21%
    assert res.casillas["03"] == "210.00"  # cuota 21%
    assert res.casillas["04"] == "200.00"  # base 10%
    assert res.casillas["29"] == "63.00"  # cuota deducible


def test_borrador_deja_claro_que_no_es_presentacion():
    res = calcular_303([LineaIVA(base=1000, tipo=0.21, sentido="devengado")])
    texto = borrador_303_texto(res, "2026-T2")
    assert "BORRADOR" in texto
    assert "no una presentación" in texto


def test_procesar_303_abre_expediente_pendiente_de_aprobacion(tmp_path):
    store = ExpedienteStore(entity_id="acme", base_dir=tmp_path)
    exp, res = procesar_303(
        store,
        [
            LineaIVA(base=1000, tipo=0.21, sentido="devengado"),
            LineaIVA(base=500, tipo=0.21, sentido="soportado"),
        ],
        periodo="2026-T2",
    )
    # fiscal nunca se auto-completa: queda esperando validación humana
    assert exp.status == ExpedienteStatus.PENDING_APPROVAL
    assert exp.kind == "fiscal_303"
    assert exp.data["resultado"] == "105.00"
    assert "borrador" in exp.data
    # trazabilidad íntegra con el evento del cálculo
    kinds = [e.kind for e in store.events(exp.id)]
    assert "calculo_303" in kinds
    assert store.verify_chain(exp.id) is True


# ── Goldens que matan a los 4 mutantes supervivientes de modelo_303.py ───────
# golden-source: Ley 37/1992 arts. 90-91 (cuota = base × tipo legal) y contrato del
# borrador documentado en el propio enunciado del módulo (A INGRESAR / A COMPENSAR).


def test_cuota_declarada_que_cuadra_no_genera_aviso_de_discrepancia():
    """Mata :85 — si la factura declara la cuota correcta, NO hay aviso de discrepancia."""
    res = calcular_303(
        [LineaIVA(base=1000, tipo=0.21, sentido="devengado", cuota=Decimal("210.00"))]
    )
    assert not any("Discrepancia" in a for a in res.avisos)
    res2 = calcular_303(
        [LineaIVA(base=1000, tipo=0.21, sentido="devengado", cuota=Decimal("250.00"))]
    )
    assert any("Discrepancia" in a for a in res2.avisos)


def test_linea_sin_concepto_se_etiqueta_linea_en_los_avisos():
    """Mata :77 — sin concepto, el aviso usa la etiqueta por defecto 'línea'."""
    res = calcular_303([LineaIVA(base=100, tipo=0.30, sentido="devengado")])
    assert any("'línea'" in a for a in res.avisos)


def test_borrador_marca_a_ingresar_y_a_compensar():
    """Mata :129 y :131 — el signo del resultado gobierna el rótulo del borrador."""
    res_pos = calcular_303([LineaIVA(base=1000, tipo=0.21, sentido="devengado")])
    assert "A INGRESAR" in borrador_303_texto(res_pos, "2T 2026")
    res_neg = calcular_303([LineaIVA(base=1000, tipo=0.21, sentido="soportado")])
    assert "A COMPENSAR/DEVOLVER" in borrador_303_texto(res_neg, "2T 2026")
