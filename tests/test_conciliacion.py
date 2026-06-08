"""Tests de conciliación bancaria (Skill W Administration Core).

Dos bloques:
- **Parser Norma 43**: el fixture coloca cada campo en su posición exacta del estándar
  (registros de 80 posiciones), de modo que se ejercita el parser contra el layout real.
- **Matcher con semáforo de confianza**: casa abonos contra partidas pendientes de cobro,
  comprobando cada tier (ALTA/MEDIA/BAJA/ABSTENCIÓN) y la abstención honesta.
"""

from datetime import date
from decimal import Decimal

from loombit_operator.conciliacion import (
    ConfianzaTier,
    Movimiento,
    Pendiente,
    _fecha,
    _imp,
    _signo,
    conciliar,
    parse_norma43,
)


def _line(parts: list[tuple[int, str]]) -> str:
    """Compone una línea N43 de 80 posiciones colocando cada (inicio_0based, valor)."""
    row = [" "] * 80
    for start, val in parts:
        for i, ch in enumerate(val):
            row[start + i] = ch
    return "".join(row)


# ── Bloque de una cuenta: cabecera 11, dos movimientos 22 (+23), final 33 ──────
_REG_11 = _line(
    [
        (0, "11"),
        (2, "2100"),
        (6, "0418"),
        (10, "0200051332"),
        (20, "240101"),
        (26, "240131"),
        (32, "2"),
        (33, "00000000100000"),
        (47, "978"),
        (50, "3"),
        (51, "CAIXABANK SA"),
    ]
)
_REG_22_CARGO = _line(
    [
        (0, "22"),
        (2, "0418"),
        (6, "240115"),
        (12, "240116"),
        (18, "12"),
        (20, "001"),
        (23, "1"),
        (24, "00000000025050"),
        (38, "0000000001"),
        (48, "FRA2024-007"),
        (60, "ACME SL"),
    ]
)
_REG_23_CARGO = _line(
    [(0, "23"), (2, "01"), (4, "PAGO FACTURA FRA2024-007"), (42, "PROVEEDOR ACME SL")]
)
_REG_22_ABONO = _line(
    [
        (0, "22"),
        (2, "0418"),
        (6, "240120"),
        (12, "240120"),
        (18, "06"),
        (20, "002"),
        (23, "2"),
        (24, "00000000050000"),
        (38, "0000000002"),
        (48, "REC-0042"),
        (60, "CLIENTE BETA SA"),
    ]
)
_REG_33 = _line(
    [
        (0, "33"),
        (2, "0418"),
        (6, "00001"),
        (11, "00000000025050"),
        (25, "00001"),
        (30, "00000000050000"),
        (44, "2"),
        (45, "00000000124950"),
    ]
)
_REG_88 = _line([(0, "88"), (20, "000007")])

EXTRACTO_OK = "\n".join([_REG_11, _REG_22_CARGO, _REG_23_CARGO, _REG_22_ABONO, _REG_33, _REG_88])


# ── helpers unitarios del parser ─────────────────────────────────────────────────
def test_imp_dos_decimales_implicitos():
    assert _imp("00000000123456") == Decimal("1234.56")
    assert _imp("00000000000000") == Decimal("0.00")


def test_signo_debe_es_negativo_haber_positivo():
    assert _signo("1") == -1  # debe / cargo
    assert _signo("2") == 1  # haber / abono


def test_fecha_pivote_de_siglo():
    assert _fecha("240115") == date(2024, 1, 15)
    assert _fecha("991231") == date(1999, 12, 31)


# ── parser ──────────────────────────────────────────────────────────────────────
def test_parsea_cabecera_y_dos_movimientos():
    cuentas = parse_norma43(EXTRACTO_OK)
    assert len(cuentas) == 1
    c = cuentas[0]
    assert c.entidad == "2100"
    assert c.cuenta == "0200051332"
    assert c.saldo_inicial == Decimal("1000.00")
    assert c.saldo_final == Decimal("1249.50")
    assert len(c.movimientos) == 2


def test_signos_y_fechas_de_los_movimientos():
    c = parse_norma43(EXTRACTO_OK)[0]
    cargo, abono = c.movimientos
    assert cargo.importe == Decimal("-250.50")
    assert cargo.es_abono is False
    assert cargo.fecha_operacion == date(2024, 1, 15)
    assert abono.importe == Decimal("500.00")
    assert abono.es_abono is True


def test_concepto_libre_del_registro_23_se_consolida():
    cargo = parse_norma43(EXTRACTO_OK)[0].movimientos[0]
    assert "FRA2024-007" in cargo.texto  # de la referencia
    assert "PAGO FACTURA FRA2024-007" in cargo.conceptos  # del registro 23
    assert "ACME" in cargo.texto


def test_totales_abonos_y_cargos():
    c = parse_norma43(EXTRACTO_OK)[0]
    assert c.total_abonos == Decimal("500.00")
    assert c.total_cargos == Decimal("250.50")


def test_extracto_correcto_cuadra_sin_avisos():
    c = parse_norma43(EXTRACTO_OK)[0]
    assert c.cuadra is True
    assert c.avisos == []


def test_lineas_cortas_se_toleran():
    # mismas líneas pero sin el relleno a 80 (como exporta algún banco)
    texto = "\n".join(s.rstrip() for s in EXTRACTO_OK.splitlines())
    c = parse_norma43(texto)[0]
    assert len(c.movimientos) == 2
    assert c.cuadra is True


def test_saldo_que_no_cuadra_genera_aviso_no_se_oculta():
    reg33_malo = _line(
        [
            (0, "33"),
            (2, "0418"),
            (6, "00001"),
            (11, "00000000025050"),
            (25, "00001"),
            (30, "00000000050000"),
            (44, "2"),
            (45, "00000000130000"),
        ]
    )  # saldo final declarado 1300.00 en vez de 1249.50
    texto = "\n".join([_REG_11, _REG_22_CARGO, _REG_22_ABONO, reg33_malo])
    c = parse_norma43(texto)[0]
    assert c.cuadra is False
    assert any("no cuadra" in a.lower() for a in c.avisos)


def test_numero_de_apuntes_discordante_avisa():
    reg33_malo = _line(
        [
            (0, "33"),
            (2, "0418"),
            (6, "00002"),
            (11, "00000000025050"),
            (25, "00001"),
            (30, "00000000050000"),
            (44, "2"),
            (45, "00000000124950"),
        ]
    )  # declara 2 apuntes al debe cuando solo hay 1
    texto = "\n".join([_REG_11, _REG_22_CARGO, _REG_22_ABONO, reg33_malo])
    c = parse_norma43(texto)[0]
    assert any("apuntes" in a.lower() for a in c.avisos)


def test_multiples_cuentas_en_un_fichero():
    reg_11_b = _line(
        [
            (0, "11"),
            (2, "2100"),
            (6, "0418"),
            (10, "0299999999"),
            (20, "240101"),
            (26, "240131"),
            (32, "2"),
            (33, "00000000050000"),
            (47, "978"),
            (50, "3"),
            (51, "CAIXABANK SA"),
        ]
    )
    reg_33_b = _line(
        [
            (0, "33"),
            (2, "0418"),
            (6, "00000"),
            (11, "00000000000000"),
            (25, "00001"),
            (30, "00000000050000"),
            (44, "2"),
            (45, "00000000100000"),
        ]
    )
    texto = "\n".join(
        [_REG_11, _REG_22_CARGO, _REG_22_ABONO, _REG_33, reg_11_b, _REG_22_ABONO, reg_33_b]
    )
    cuentas = parse_norma43(texto)
    assert len(cuentas) == 2
    assert cuentas[1].cuenta == "0299999999"
    assert cuentas[1].cuadra is True


def test_movimiento_texto_ignora_campos_vacios():
    m = Movimiento(
        fecha_operacion=date(2024, 1, 1),
        fecha_valor=date(2024, 1, 1),
        importe=Decimal("10.00"),
        concepto_comun="06",
        concepto_propio="002",
        num_documento="0000000001",
        referencia1="REC-1",
        referencia2="",
    )
    assert m.texto == "REC-1"


# ── matcher: helpers ──────────────────────────────────────────────────────────────
def _abono(importe: str, concepto: str) -> Movimiento:
    return Movimiento(
        fecha_operacion=date(2024, 1, 20),
        fecha_valor=date(2024, 1, 20),
        importe=Decimal(importe),
        concepto_comun="06",
        concepto_propio="002",
        num_documento="0000000002",
        referencia1="",
        referencia2="",
        conceptos=[concepto],
    )


def _pend(id_: str, importe: str, referencia: str = "", contraparte: str = "") -> Pendiente:
    return Pendiente(
        id=id_, importe=Decimal(importe), referencia=referencia, contraparte=contraparte
    )


# ── matcher: tiers ────────────────────────────────────────────────────────────────
def test_alta_importe_exacto_mas_referencia():
    mov = _abono("500.00", "TRANSFERENCIA PAGO FRA2024-007 GRACIAS")
    facturas = [_pend("f1", "500.00", referencia="FRA2024-007", contraparte="ACME SL")]
    c = conciliar([mov], facturas)[0]
    assert c.tier is ConfianzaTier.ALTA
    assert c.pendiente is not None and c.pendiente.id == "f1"
    assert c.score == 1.0


def test_media_importe_exacto_mas_contraparte_sin_referencia():
    mov = _abono("500.00", "TRANSFERENCIA DE GARCIA HERMANOS")
    facturas = [_pend("f1", "500.00", referencia="FRA-999", contraparte="GARCIA HNOS SL")]
    c = conciliar([mov], facturas)[0]
    assert c.tier is ConfianzaTier.MEDIA
    assert c.pendiente.id == "f1"


def test_media_candidato_unico_sin_pistas_en_concepto():
    mov = _abono("123.45", "ABONO VARIOS")
    facturas = [_pend("f1", "123.45", referencia="X1", contraparte="DESCONOCIDO SL")]
    c = conciliar([mov], facturas)[0]
    assert c.tier is ConfianzaTier.MEDIA


def test_abstencion_importe_ambiguo_varias_facturas_iguales():
    mov = _abono("100.00", "TRANSFERENCIA RECIBIDA SIN CONCEPTO")
    facturas = [
        _pend("f1", "100.00", referencia="A1", contraparte="ALPHA SL"),
        _pend("f2", "100.00", referencia="B2", contraparte="BETA SL"),
    ]
    c = conciliar([mov], facturas)[0]
    assert c.tier is ConfianzaTier.ABSTENCION
    assert c.pendiente is None


def test_abstencion_sin_candidato_de_importe():
    mov = _abono("999.99", "TRANSFERENCIA RARA")
    facturas = [_pend("f1", "100.00", contraparte="ACME SL")]
    c = conciliar([mov], facturas)[0]
    assert c.tier is ConfianzaTier.ABSTENCION


def test_baja_pago_parcial_con_referencia():
    mov = _abono("300.00", "PAGO A CUENTA FRA2024-007")
    facturas = [_pend("f1", "800.00", referencia="FRA2024-007", contraparte="ACME SL")]
    c = conciliar([mov], facturas)[0]
    assert c.tier is ConfianzaTier.BAJA
    assert c.pendiente.id == "f1"
    assert "parcial" in c.razon.lower()


def test_baja_pago_agrupado_n_a_1():
    mov = _abono("500.00", "TRANSFERENCIA DE OMEGA SL VARIAS FACTURAS")
    facturas = [
        _pend("f1", "300.00", referencia="A1", contraparte="OMEGA SL"),
        _pend("f2", "200.00", referencia="A2", contraparte="OMEGA SL"),
    ]
    c = conciliar([mov], facturas)[0]
    assert c.tier is ConfianzaTier.BAJA
    assert {p.id for p in c.grupo} == {"f1", "f2"}


def test_cargo_queda_fuera_de_alcance():
    cargo = Movimiento(
        fecha_operacion=date(2024, 1, 15),
        fecha_valor=date(2024, 1, 15),
        importe=Decimal("-250.50"),
        concepto_comun="12",
        concepto_propio="001",
        num_documento="0000000001",
        referencia1="",
        referencia2="",
        conceptos=["PAGO PROVEEDOR"],
    )
    c = conciliar([cargo], [_pend("f1", "250.50")])[0]
    assert c.tier is ConfianzaTier.ABSTENCION
    assert "cargo" in c.razon.lower()


def test_referencia_robusta_a_separadores():
    # 'FRA 2024 007' en el concepto casa con la referencia 'FRA2024-007' (forma compacta).
    mov = _abono("500.00", "PAGO FRA 2024 007")
    facturas = [_pend("f1", "500.00", referencia="FRA2024-007", contraparte="ACME SL")]
    assert conciliar([mov], facturas)[0].tier is ConfianzaTier.ALTA


def test_alias_resolver_desambigua_lo_que_de_otro_modo_se_abstiene():
    """La costura del flywheel: un resolver que mapea el concepto opaco a la contraparte
    conocida convierte una abstención (dos importes iguales) en un match MEDIA."""

    class _ResolverStub:
        def __init__(self, mapa):
            self.mapa = mapa

        def canonico(self, texto):
            for clave, canon in self.mapa.items():
                if clave in texto:
                    return canon
            return None

    mov = _abono("100.00", "TRANSFERENCIA REF 880055")
    facturas = [
        _pend("f1", "100.00", referencia="A1", contraparte="ALPHA SL"),
        _pend("f2", "100.00", referencia="B2", contraparte="BETA SISTEMAS SL"),
    ]
    # Sin resolver: ambiguo → abstención.
    assert conciliar([mov], facturas)[0].tier is ConfianzaTier.ABSTENCION
    # Con resolver: el concepto 880055 ES "BETA SISTEMAS" → MEDIA sobre f2.
    resolver = _ResolverStub({"880055": "BETA SISTEMAS"})
    c = conciliar([mov], facturas, alias_resolver=resolver)[0]
    assert c.tier is ConfianzaTier.MEDIA
    assert c.pendiente.id == "f2"
