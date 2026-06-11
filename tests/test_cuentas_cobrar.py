"""
Store de cuentas a cobrar (Fase 2): pendientes, vencidas y próximas (con `today` fijo).
"""

# golden-source: enunciado docs/BANCO_SUPUESTOS_LOOMBIT.md (S-03: clasificación por-vencer / vencida con `today` fijo).

import pytest

from loombit_operator.cuentas_cobrar import (
    CuentaCobrar,
    CuentasCobrarStore,
    cuenta_desde_factura,
)


def _store(tmp_path):
    return CuentasCobrarStore(path=tmp_path / "cc.json")


def test_add_list_pendientes(tmp_path):
    s = _store(tmp_path)
    s.add(CuentaCobrar(cliente="Acme", importe=100, vencimiento="2026-06-01"))
    s.add(CuentaCobrar(cliente="Beta", importe=200, vencimiento="2026-06-20"))
    assert len(s.list()) == 2
    assert len(s.pendientes()) == 2
    # persiste y recarga
    assert len(_store(tmp_path).list()) == 2


def test_vencidas_y_proximas(tmp_path):
    s = _store(tmp_path)
    today = "2026-06-10"
    s.add(CuentaCobrar(cliente="Vencida", importe=100, vencimiento="2026-06-01"))  # 9 días vencida
    s.add(CuentaCobrar(cliente="Proxima", importe=50, vencimiento="2026-06-13"))  # vence en 3 días
    s.add(CuentaCobrar(cliente="Lejana", importe=70, vencimiento="2026-07-30"))  # lejos
    assert [c.cliente for c in s.vencidas(today)] == ["Vencida"]
    assert [c.cliente for c in s.proximas(7, today)] == ["Proxima"]


def test_cuenta_desde_factura_solo_emitida():
    c = cuenta_desde_factura(proveedor="Acme", total=500, sentido="devengado", numero="F-1")
    assert c is not None
    assert c.cliente == "Acme" and c.importe == 500 and "F-1" in c.concepto and c.vencimiento
    # recibida (compra) → no se cobra
    assert cuenta_desde_factura(proveedor="X", total=500, sentido="soportado") is None
    # sin importe → nada
    assert cuenta_desde_factura(proveedor="X", total=None, sentido="devengado") is None


def test_marcar_cobrada(tmp_path):
    s = _store(tmp_path)
    c = s.add(CuentaCobrar(cliente="X", importe=10, vencimiento="2026-06-01"))
    assert s.marcar_cobrada(c.id) is True
    assert s.pendientes() == []
    assert s.marcar_cobrada("noexiste") is False


def test_conciliar_cobro_por_referencia(tmp_path):
    s = _store(tmp_path)
    s.add(
        CuentaCobrar(
            cliente="Acme SL", importe=500, vencimiento="2026-06-01", concepto="Factura F-7"
        )
    )
    assert s.conciliar_cobro(referencia="F-7") is not None
    assert s.pendientes() == []


def test_conciliar_cobro_por_cliente_importe(tmp_path):
    s = _store(tmp_path)
    s.add(CuentaCobrar(cliente="Beta SL", importe=300, vencimiento="2026-06-01"))
    assert s.conciliar_cobro(cliente="Beta SL", importe=300) is not None
    assert s.pendientes() == []
    # sin coincidencia → None
    s.add(CuentaCobrar(cliente="Gamma", importe=100, vencimiento="2026-06-01"))
    assert s.conciliar_cobro(cliente="Nadie", importe=999) is None


# ── Arnés de los 4 bugs (golden ANTES de arreglar; esperado desde el dominio) ────────


def test_conciliar_referencia_no_casa_por_subcadena(tmp_path):
    """Bug 1: la referencia casa como TOKEN, no como subcadena.
    'F-7' NO debe conciliar 'Factura F-70' (es otra factura distinta)."""
    s = _store(tmp_path)
    s.add(
        CuentaCobrar(cliente="Acme", importe=700, vencimiento="2026-06-01", concepto="Factura F-70")
    )
    assert s.conciliar_cobro(referencia="F-7") is None  # no existe la F-7
    assert len(s.pendientes()) == 1  # la F-70 sigue intacta
    # la referencia exacta sí concilia
    assert s.conciliar_cobro(referencia="F-70") is not None
    assert s.pendientes() == []


def test_conciliar_referencia_elige_el_token_exacto(tmp_path):
    """Conviviendo F-7 y F-70, 'F-7' concilia exactamente la F-7 (no la F-70)."""
    s = _store(tmp_path)
    a = s.add(
        CuentaCobrar(cliente="Acme", importe=700, vencimiento="2026-06-01", concepto="Factura F-70")
    )
    b = s.add(
        CuentaCobrar(cliente="Beta", importe=70, vencimiento="2026-06-02", concepto="Factura F-7")
    )
    assert s.conciliar_cobro(referencia="F-7") == b.id
    assert [c.id for c in s.pendientes()] == [a.id]  # la F-70 sigue pendiente


def test_importe_negativo_rechazado_en_creacion():
    """Bug 2: un importe negativo es imposible (te deben, no debes). Se rechaza al crear."""
    with pytest.raises(ValueError):
        CuentaCobrar(cliente="X", importe=-100, vencimiento="2026-06-01")


def test_importe_negativo_no_entra_desde_factura():
    """Una factura con total negativo no genera cuenta a cobrar."""
    assert cuenta_desde_factura(proveedor="X", total=-500, sentido="devengado") is None


def test_load_omite_fila_corrupta_sin_tumbar_el_store(tmp_path):
    """Bug 2/3: una fila corrupta en disco (importe negativo) se omite; el resto carga."""
    p = tmp_path / "cc.json"
    p.write_text(
        '[{"id":"good","cliente":"Acme","importe":100,"vencimiento":"2026-06-01",'
        '"concepto":"","estado":"pendiente"},'
        '{"id":"bad","cliente":"Mala","importe":-9,"vencimiento":"2026-06-01",'
        '"concepto":"","estado":"pendiente"}]',
        encoding="utf-8",
    )
    s = CuentasCobrarStore(path=p)
    ids = [c.id for c in s.list()]
    assert "good" in ids  # la fila buena no se pierde por culpa de la corrupta
    assert "bad" not in ids


def test_vencidas_no_revienta_con_fecha_ilegible(tmp_path):
    """Bug 3: una fila con fecha ilegible NO revienta vencidas()/proximas();
    se omite de la clasificación pero el listado sigue vivo."""
    s = _store(tmp_path)
    today = "2026-06-10"
    s.add(CuentaCobrar(cliente="Buena", importe=100, vencimiento="2026-06-01"))  # vencida
    s.add(CuentaCobrar(cliente="Ilegible", importe=50, vencimiento="ayer por la tarde"))
    assert [c.cliente for c in s.vencidas(today)] == ["Buena"]  # no lanza
    assert s.proximas(7, today) == []  # tampoco revienta
    # la ilegible no se pierde: sigue como pendiente, solo no se clasifica
    assert any(c.cliente == "Ilegible" for c in s.pendientes())


def test_conciliar_cliente_no_casa_por_subcadena(tmp_path):
    """Bug 4: el cliente casa por token, no por subcadena. 'Ana' NO concilia 'Anabel SL'."""
    s = _store(tmp_path)
    s.add(CuentaCobrar(cliente="Anabel SL", importe=300, vencimiento="2026-06-01"))
    assert s.conciliar_cobro(cliente="Ana", importe=300) is None
    assert len(s.pendientes()) == 1


def test_conciliar_cliente_sin_sufijo_societario_si_casa(tmp_path):
    """El nombre sin el sufijo societario sí concilia ('Beta' ↔ 'Beta SL')."""
    s = _store(tmp_path)
    s.add(CuentaCobrar(cliente="Beta SL", importe=300, vencimiento="2026-06-01"))
    assert s.conciliar_cobro(cliente="Beta", importe=300) is not None
    assert s.pendientes() == []
