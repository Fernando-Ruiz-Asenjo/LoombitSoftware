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


def test_registrar_factura_registrada_y_enrutada():
    names = {t.name for t in tool_registry.list()}
    assert "registrar_factura" in names
    assert "registrar_factura" in select_tool_names("emite una factura a un cliente")


def test_303_desde_registradas_sin_facturas_abstiene():
    import shutil

    from loombit_operator.config import get_settings
    from loombit_operator.tools import dominio

    ent = "_test_303_vacia"
    base = get_settings().entities_dir / ent
    shutil.rmtree(base, ignore_errors=True)
    orig = dominio._ENTIDAD_DEFECTO
    dominio._ENTIDAD_DEFECTO = ent
    try:
        out = dominio._calcular_303_registradas()
        assert "No tienes facturas registradas" in out
    finally:
        dominio._ENTIDAD_DEFECTO = orig
        shutil.rmtree(base, ignore_errors=True)


def test_303_desde_registradas_calcula_con_datos_reales():
    import shutil

    from loombit_operator.config import get_settings
    from loombit_operator.tools import dominio

    ent = "_test_303_real"
    base = get_settings().entities_dir / ent
    shutil.rmtree(base, ignore_errors=True)
    orig = dominio._ENTIDAD_DEFECTO
    dominio._ENTIDAD_DEFECTO = ent
    try:
        # fecha dentro del 2T 2026: el 303 de un trimestre solo cuenta facturas de ESE trimestre
        dominio._registrar_factura(
            contraparte="Cliente A", base=1000, tipo=21, sentido="emitida", fecha="2026-05-15"
        )
        dominio._registrar_factura(
            contraparte="Proveedor B", base=200, tipo=21, sentido="recibida", fecha="2026-05-20"
        )
        # una factura de OTRO trimestre (1T) NO debe colarse en el 2T
        dominio._registrar_factura(
            contraparte="Cliente Viejo", base=5000, tipo=21, sentido="emitida", fecha="2026-02-01"
        )
        out = dominio._calcular_303_registradas("2T 2026")
        assert "2 factura" in out  # solo las 2 del 2T (la del 1T queda fuera)
        assert "210" in out  # IVA devengado 1000@21
        assert "42" in out  # IVA deducible 200@21
        assert "168" in out  # resultado 210-42 a ingresar
        assert "1050" not in out  # NO debe aparecer el IVA de la factura del 1T (5000@21)
    finally:
        dominio._ENTIDAD_DEFECTO = orig
        shutil.rmtree(base, ignore_errors=True)


def test_resumen_facturacion_suma_solo_emitidas_del_periodo():
    import shutil

    from loombit_operator.config import get_settings
    from loombit_operator.tools import dominio

    ent = "_test_facturacion"
    base = get_settings().entities_dir / ent
    shutil.rmtree(base, ignore_errors=True)
    orig = dominio._ENTIDAD_DEFECTO
    dominio._ENTIDAD_DEFECTO = ent
    try:
        dominio._registrar_factura(
            contraparte="A", base=1000, tipo=21, sentido="emitida", fecha="2026-06-05"
        )
        dominio._registrar_factura(
            contraparte="B", base=2000, tipo=21, sentido="emitida", fecha="2026-06-08"
        )
        # una recibida (NO cuenta como facturado) y una emitida de OTRO mes (fuera del periodo)
        dominio._registrar_factura(
            contraparte="Prov", base=500, tipo=21, sentido="recibida", fecha="2026-06-09"
        )
        dominio._registrar_factura(
            contraparte="C", base=9000, tipo=21, sentido="emitida", fecha="2026-05-30"
        )
        out = dominio._resumen_facturacion("junio 2026")
        assert "2 factura" in out  # solo las 2 emitidas de junio
        assert "3000" in out  # base 1000+2000 (recibida y mayo excluidas)
        assert "3630" in out  # total con IVA
        assert "9000" not in out  # la de mayo NO se cuela
    finally:
        dominio._ENTIDAD_DEFECTO = orig
        shutil.rmtree(base, ignore_errors=True)


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


def test_calcular_303_rechaza_tipo_de_iva_imposible():
    # Antifabricación: un 40% de IVA no existe → no se calcula un 303 falso, se rechaza.
    out = _calcular_303(iva_soportado=[{"base": 7000, "tipo": 40, "concepto": "Contratación"}])
    assert "ERROR" in out
    assert "no válido" in out.lower()
    assert "7000" not in out  # no calcula con el dato inventado


def test_calcular_303_echo_muestra_las_lineas_usadas():
    # Visibilidad: el resultado deja ver con qué se calculó (delata líneas inventadas).
    out = _calcular_303(
        iva_repercutido=[{"base": 12000, "tipo": 21, "concepto": "Ventas"}],
        iva_soportado=[{"base": 3000, "tipo": 21, "concepto": "Compras"}],
    )
    assert "Calculado con" in out
    assert "12000" in out and "3000" in out
    assert "1890" in out  # 2520 devengado - 630 deducible = 1890 a ingresar
