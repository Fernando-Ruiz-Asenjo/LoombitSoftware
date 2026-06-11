"""
Fase 3 · intake: el eslabón que faltaba — de una factura (texto/PDF) AL REGISTRO para el 303.
Antes el extractor leía y el registro pedía campos a mano; aquí se unen: suelta la factura y entra
en el pipeline. Abstención honesta si no es legible (se registra, pero se marca para revisar).
"""

from fastapi.testclient import TestClient

from loombit_operator.expedientes import ExpedienteStore
from loombit_operator.main import app
from loombit_operator.skill_d_fiscal.intake import registrar_factura_desde_texto

_FACTURA = (
    "Acme Servicios SL\n"
    "Factura F-2026-9\n"
    "Fecha de factura: 03/02/2026\n"
    "Base imponible: 1.000,00\n"
    "IVA: 210,00\n"
    "Total: 1.210,00\n"
)


def test_extrae_y_registra_factura_desde_texto(tmp_path):
    store = ExpedienteStore(entity_id="acme", base_dir=tmp_path)
    exp, inv, avisos = registrar_factura_desde_texto(store, _FACTURA, "soportado")
    assert exp.kind == "factura_intake"
    assert inv.base_imponible == 1000.0
    assert inv.iva == 210.0
    assert store.verify_chain(exp.id) is True
    assert avisos == []  # legible → sin avisos de abstención


def test_factura_ilegible_se_registra_pero_avisa(tmp_path):
    store = ExpedienteStore(entity_id="acme", base_dir=tmp_path)
    exp, inv, avisos = registrar_factura_desde_texto(
        store, "hola, esto no es una factura", "soportado"
    )
    assert exp.kind == "factura_intake"
    assert inv.base_imponible is None
    assert any("revisar" in a.lower() for a in avisos)  # honesto: no inventa, marca para revisar


def test_endpoint_factura_desde_documento(tmp_path, monkeypatch):
    # Aísla el store de la entidad en tmp (no toca runtime real).
    import loombit_operator.routers.fiscal as fr

    monkeypatch.setattr(
        fr, "_store", lambda entity_id: ExpedienteStore(entity_id=entity_id, base_dir=tmp_path)
    )
    client = TestClient(app)
    r = client.post(
        "/entidades/acme/facturas/desde-documento",
        json={"sentido": "soportado", "text": _FACTURA},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "factura_intake"
    assert body["campos"]["base_imponible"] == 1000.0
    assert body["avisos"] == []
