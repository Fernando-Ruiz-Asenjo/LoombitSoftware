"""
Store de cuentas a cobrar (Fase 2): pendientes, vencidas y próximas (con `today` fijo).
"""

from loombit_operator.cuentas_cobrar import CuentaCobrar, CuentasCobrarStore


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


def test_marcar_cobrada(tmp_path):
    s = _store(tmp_path)
    c = s.add(CuentaCobrar(cliente="X", importe=10, vencimiento="2026-06-01"))
    assert s.marcar_cobrada(c.id) is True
    assert s.pendientes() == []
    assert s.marcar_cobrada("noexiste") is False
