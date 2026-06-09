"""
Tools de dominio (cobro / 303) expuestas al agente: deben calcular con los cerebros
deterministas y estar registradas + enrutadas para que el agente las alcance.
"""

from loombit_operator.tools import tool_registry
from loombit_operator.tools.dominio import _calcular_303, _plan_cobro
from loombit_operator.tools.registry import select_tool_names


def test_plan_cobro_registrada_y_enrutada():
    names = {t.name for t in tool_registry.list()}
    assert "plan_cobro" in names
    assert "plan_cobro" in select_tool_names("reclama el cobro de una factura vencida")


def test_303_registrada_y_enrutada():
    names = {t.name for t in tool_registry.list()}
    assert "calcular_303" in names
    assert "calcular_303" in select_tool_names("cómo va el 303 de este trimestre")


def test_travel_task_alcanza_el_pilot():
    # El motor de viajes es el Pilot: la petición de vuelos debe darle manos de navegador.
    names = select_tool_names("búscame vuelos a Londres y un hotel para Marta")
    assert "browser_navigate" in names
    assert "browser_read_page" in names


def test_plan_cobro_factura_vencida_calcula_interes_y_compensacion():
    out = _plan_cobro(1500, "2026-05-01", tipo_interes_anual=10.0)
    assert "1500" in out
    assert "40" in out  # compensación fija legal
    assert "€" in out
    assert "reclam" in out.lower()


def test_plan_cobro_respeta_cobro_parcial():
    # total 2000, cobrado 800 → solo se reclama el saldo (1200)
    out = _plan_cobro(2000, "2020-01-01", cobrado=800)
    assert "1200" in out


def test_plan_cobro_factura_cobrada_no_reclama():
    out = _plan_cobro(1000, "2020-01-01", cobrado=1000)
    assert "cobrada" in out.lower()


def test_calcular_303_devengado_menos_deducible():
    out = _calcular_303(
        iva_repercutido=[{"base": 3000, "tipo": 21}],
        iva_soportado=[{"base": 1000, "tipo": 21}],
        periodo="2T 2026",
    )
    assert "630" in out  # IVA devengado
    assert "210" in out  # IVA deducible
    assert "420" in out  # resultado a ingresar
    assert "BORRADOR" in out


def test_calcular_303_acepta_tipo_en_fraccion_o_porcentaje():
    a = _calcular_303(iva_repercutido=[{"base": 1000, "tipo": 21}])
    b = _calcular_303(iva_repercutido=[{"base": 1000, "tipo": 0.21}])
    assert "210" in a and "210" in b
