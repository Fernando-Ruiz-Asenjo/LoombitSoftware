"""Tests del intake fiscal: factura extraída → línea de IVA → 303, con abstención honesta."""

from datetime import date
from decimal import Decimal

from loombit_operator.docs_intel import InvoiceFields
from loombit_operator.expedientes import ExpedienteStatus, ExpedienteStore
from loombit_operator.skill_d_fiscal.intake import (
    rango_periodo,
    rango_trimestre,
    recopilar_lineas,
)
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
    assert inferir_tipo_iva(0, 0) is None  # base inválida (cero, no se puede inferir)


def test_inferir_tipo_acepta_rectificativas_negativas():
    # devolución/abono: base e IVA negativos → tipo por valor absoluto (antes daba None y se caía del 303)
    assert inferir_tipo_iva(-200, -42) == Decimal("0.21")
    assert inferir_tipo_iva(-100, -10) == Decimal("0.10")
    assert inferir_tipo_iva(-200, -50) is None  # 25% sigue sin ser estándar


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


# ── Regresión de la auditoría adversarial 2026-06-11 ─────────────────────────
# golden-source: Ley 37/1992 del IVA, arts. 90-91 (tipos 21/10/4/0) y convención
# de fecha dd/mm/aaaa de la factura española (enunciado: el extractor docs_intel
# emite ese formato y el 303 trimestral debe incluir esas facturas).


def test_factura_con_fecha_espanola_entra_en_su_trimestre(tmp_path):
    """T1: '15/04/2026' debe contarse en el 2T 2026 (antes se excluía como ilegible)."""
    store = ExpedienteStore(entity_id="acme", base_dir=tmp_path)
    inv = InvoiceFields(numero="F-1", base_imponible=1000.0, iva=210.0, fecha="15/04/2026")
    registrar_factura(store, inv, "devengado")
    _, res = liquidar_303_periodo(store, "2T 2026")
    assert res.iva_devengado == Decimal("210.00")  # 1000 × 21% (art. 90.Uno)


def test_factura_duplicada_no_se_suma_dos_veces(tmp_path):
    """T2: el mismo nº de factura registrado 2 veces cuenta UNA vez y deja aviso."""
    store = ExpedienteStore(entity_id="acme", base_dir=tmp_path)
    inv = InvoiceFields(numero="F-DUP", base_imponible=1000.0, iva=210.0, fecha="2026-04-15")
    registrar_factura(store, inv, "devengado")
    registrar_factura(store, inv, "devengado")
    _, res = liquidar_303_periodo(store, "2T 2026")
    assert res.iva_devengado == Decimal("210.00")
    assert any("duplicada" in a for a in res.avisos)


def test_inferir_tipo_ambiguo_se_abstiene_y_exacto_gana():
    """T3: con importes diminutos varios tipos 'cuadran al céntimo' → abstención;
    pero un cuadre EXACTO único gana aunque otro tipo cuadre por tolerancia."""
    assert inferir_tipo_iva(Decimal("0.04"), Decimal("0.00")) is None  # 3 cuadres exactos
    assert inferir_tipo_iva(Decimal("0.10"), Decimal("0.01")) == Decimal("0.10")  # exacto único
    assert inferir_tipo_iva(Decimal("1000"), Decimal("210.00")) == Decimal("0.21")


# ── Goldens que matan a los 13 mutantes supervivientes de intake.py ──────────
# golden-source: contrato documentado en los docstrings de intake.py (enunciado:
# periodo None/sin trimestre NO filtra y etiqueta honesto; «este mes»/«mes actual»/
# «del mes»/«este_mes» = mes en curso) y Ley 37/1992 arts. 90-91 (tipos).


def test_rango_trimestre_sin_periodo_no_revienta_y_etiqueta_honesto():
    """Mata :33 y :44 — periodo None / sin trimestre → (None, None, etiqueta legible)."""
    assert rango_trimestre(None) == (None, None, "todas las facturas")
    d, h, et = rango_trimestre("lo que sea sin trimestre")
    assert d is None and h is None
    assert et == "lo que sea sin trimestre"


def test_rango_periodo_none_y_texto_libre():
    """Mata :76, :80 y :86 — None → 'todo'; texto sin mes → la etiqueta es el texto."""
    assert rango_periodo(None) == (None, None, "todo")
    assert rango_periodo("xyz")[2] == "xyz"
    d, _, _ = rango_periodo("este mes")  # sin 'hoy' explícito: usa la fecha actual
    assert d == date.today().replace(day=1)


def test_rango_periodo_sinonimos_de_mes_en_curso():
    """Mata los tres or de :81 — cada sinónimo resuelve al mes en curso."""
    hoy = date(2026, 6, 11)
    for alias in ("mes actual", "del mes", "este_mes"):
        d, h, et = rango_periodo(alias, hoy)
        assert d == date(2026, 6, 1), alias
        assert h == date(2026, 6, 30), alias


def test_inferir_tipo_por_tolerancia_al_centimo():
    """Mata :115 — sin cuadre exacto, un único candidato al céntimo se acepta."""
    assert inferir_tipo_iva(Decimal("100"), Decimal("21.01")) == Decimal("0.21")


# golden-source: calendario de presentación del modelo 303 (AEAT — la
# autoliquidación de un trimestre se presenta una vez TERMINADO ese trimestre;
# el 4T se presenta entre el 1 y el 30 de enero del año SIGUIENTE). Enunciado:
# un trimestre pedido SIN año se refiere al último que ya ha concluido, no al
# del año en curso si ese aún no ha terminado (evita liquidar el 303 del
# trimestre equivocado — T12 de la auditoría adversarial 2026-06-11).
def test_rango_trimestre_sin_anio_usa_el_ultimo_trimestre_terminado():
    # En enero de 2026, '4T' = 4T 2025 (4T 2026 ni siquiera ha empezado a liquidarse).
    assert rango_trimestre("4T", date(2026, 1, 15)) == (
        date(2025, 10, 1),
        date(2025, 12, 31),
        "4T 2025",
    )
    # Un trimestre del año en curso YA terminado sí usa el año en curso.
    assert rango_trimestre("2T", date(2026, 8, 1)) == (
        date(2026, 4, 1),
        date(2026, 6, 30),
        "2T 2026",
    )
    # Un trimestre del año en curso AÚN no terminado → el del año anterior.
    assert rango_trimestre("2T", date(2026, 5, 15))[2] == "2T 2025"
    # Con año EXPLÍCITO se respeta siempre, ignorando 'hoy'.
    assert rango_trimestre("4T 2026", date(2026, 1, 15))[2] == "4T 2026"


def test_linea_sin_numero_usa_sn_y_base_none_se_abstiene():
    """Mata :126 y :127 — sin nº → 's/n' en el aviso; base None con IVA presente → abstención."""
    linea, avisos = linea_desde_factura(
        InvoiceFields(numero=None, base_imponible=None, iva=210.0), "devengado"
    )
    assert linea is None
    assert avisos and "s/n" in avisos[0]


def test_registrar_factura_sin_numero_titula_sn(tmp_path):
    """Mata :152 — el expediente de una factura sin nº se titula 'Factura s/n'."""
    store = ExpedienteStore(entity_id="acme", base_dir=tmp_path)
    exp = registrar_factura(
        store, InvoiceFields(numero=None, base_imponible=100.0, iva=21.0), "devengado"
    )
    assert exp.title == "Factura s/n"


def test_recopilar_sin_rango_completo_no_filtra(tmp_path):
    """Mata :196 — con solo 'desde' (sin 'hasta') NO se filtra: entran todas."""
    store = ExpedienteStore(entity_id="acme", base_dir=tmp_path)
    registrar_factura(
        store,
        InvoiceFields(numero="F-A", base_imponible=1000.0, iva=210.0, fecha="2024-01-01"),
        "devengado",
    )
    lineas, _ = recopilar_lineas(store, desde=date(2026, 1, 1), hasta=None)
    assert len(lineas) == 1
