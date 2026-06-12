"""
Orquestador del lazo de cobros — golden. pendientes() solo lista; aprobar_y_enviar() envía con gate.
"""

from __future__ import annotations

from loombit_operator.cuentas_cobrar import CuentaCobrar, CuentasCobrarStore
from loombit_operator.skill_d_fiscal.cobros_flujo import aprobar_y_enviar, pendientes
from loombit_operator.skill_d_fiscal.envio_cobro import EnvioBloqueado

HOY = "2026-07-01"


def _cc(tmp_path):
    cc = CuentasCobrarStore(path=tmp_path / "cc.json")
    cc.add(CuentaCobrar(cliente="Cliente Uno SL", importe=1210.0, vencimiento="2026-06-09"))
    return cc


def test_pendientes_lista_no_envia(tmp_path):
    cc = _cc(tmp_path)
    outbox = tmp_path / "outbox"
    ds = pendientes(cc, HOY)
    assert len(ds) == 1
    assert not outbox.exists()  # listar NO envía nada


def test_aprobar_y_enviar_manda_al_outbox(tmp_path):
    cc = _cc(tmp_path)
    d = pendientes(cc, HOY)[0]
    r = aprobar_y_enviar(d, outbox_dir=tmp_path / "outbox")
    assert r["enviado"] is True and r["via"] == "outbox"
    assert list((tmp_path / "outbox").glob("*.eml"))


def test_el_gate_no_se_salta_por_el_orquestador(tmp_path):
    # aprobar_y_enviar no puede colar un € inventado: el guardia §14B sigue dentro.
    cc = _cc(tmp_path)
    d = pendientes(cc, HOY)[0]
    try:
        aprobar_y_enviar(d, cuerpo="Te debe 9999 €", outbox_dir=tmp_path / "outbox")
        raise AssertionError("debería haber bloqueado")
    except EnvioBloqueado:
        pass
    assert not (tmp_path / "outbox").exists()
