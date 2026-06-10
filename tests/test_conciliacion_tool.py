"""La tool conciliar_banco está cableada (registrada + ruteada) y abstiene con honestidad.
El motor de casado en sí se prueba en test_conciliacion.py."""

from loombit_operator.tools import tool_registry
from loombit_operator.tools.conciliacion_tool import _conciliar_banco
from loombit_operator.tools.registry import select_tool_names


def test_conciliar_banco_registrada():
    td = tool_registry.get("conciliar_banco")
    assert td.authoritative is True  # sus cifras son deterministas, no se parafrasean


def test_router_ofrece_conciliar_banco():
    assert "conciliar_banco" in select_tool_names("concilia mi banco de este mes")
    assert "conciliar_banco" in select_tool_names("cuadra los cobros con el extracto bancario")


def test_conciliar_sin_extracto_pide_n43():
    out = _conciliar_banco("")
    assert "norma 43" in out.lower()  # pide el extracto, no inventa


def test_conciliar_con_basura_dice_que_no_es_n43():
    out = _conciliar_banco("esto no es un extracto, es texto cualquiera")
    assert "norma 43" in out.lower() and "no" in out.lower()
