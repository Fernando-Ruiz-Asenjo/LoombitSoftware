"""Tests de conciliación bancaria: adaptador de cobros + flujo de router (humano en el bucle)."""

import shutil
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from loombit_operator.config import get_settings
from loombit_operator.expedientes import ExpedienteStore
from loombit_operator.main import app
from loombit_operator.skill_d_fiscal import marcar_cobrada, pendientes_de_cobro, registrar_factura
from loombit_operator.docs_intel import InvoiceFields

client = TestClient(app)


@pytest.fixture
def eid():
    e = "test_" + uuid4().hex[:8]
    yield e
    d = get_settings().entities_dir / e
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)


def _line(parts: list[tuple[int, str]]) -> str:
    row = [" "] * 80
    for start, val in parts:
        for i, ch in enumerate(val):
            row[start + i] = ch
    return "".join(row)


def _extracto_un_abono(importe_14: str, referencia: str, contraparte: str) -> str:
    """N43 mínimo que cuadra: saldo inicial 0, un único abono, registro 33 coherente."""
    reg11 = _line(
        [
            (0, "11"),
            (2, "2100"),
            (6, "0418"),
            (10, "0200051332"),
            (20, "240101"),
            (26, "240131"),
            (32, "2"),
            (33, "00000000000000"),
            (47, "978"),
            (50, "3"),
            (51, "CAIXABANK SA"),
        ]
    )
    reg22 = _line(
        [
            (0, "22"),
            (2, "0418"),
            (6, "240120"),
            (12, "240120"),
            (18, "06"),
            (20, "002"),
            (23, "2"),
            (24, importe_14),
            (38, "0000000002"),
            (48, referencia),
            (60, contraparte),
        ]
    )
    reg33 = _line(
        [
            (0, "33"),
            (2, "0418"),
            (6, "00000"),
            (11, "00000000000000"),
            (25, "00001"),
            (30, importe_14),
            (44, "2"),
            (45, importe_14),
        ]
    )
    reg88 = _line([(0, "88"), (20, "000004")])
    return "\n".join([reg11, reg22, reg33, reg88])


# ── adaptador de cobros (unidad) ──────────────────────────────────────────────────
def test_pendientes_excluye_soportado_cobrado_y_sin_importe(tmp_path):
    store = ExpedienteStore(entity_id="acme", base_dir=tmp_path)
    registrar_factura(
        store, InvoiceFields(numero="E-1", base_imponible=1000.0, iva=210.0), "devengado"
    )
    registrar_factura(
        store, InvoiceFields(numero="R-1", base_imponible=500.0, iva=105.0), "soportado"
    )
    sin_importe = registrar_factura(store, InvoiceFields(numero="E-2"), "devengado")

    pend = pendientes_de_cobro(store)
    assert [p.referencia for p in pend] == ["E-1"]  # solo la devengada con importe
    assert pend[0].importe == Decimal("1210.00")

    # al marcarla cobrada, desaparece de pendientes (alimenta el gate S-01)
    marcar_cobrada(store, pend[0].id, importe_cobrado=Decimal("1210.00"), banco_ref="x")
    assert pendientes_de_cobro(store) == []
    assert sin_importe.id  # registrada pero no conciliable (sin importe fiable)


# ── flujo de router e2e ───────────────────────────────────────────────────────────
def test_flujo_conciliacion_propuesta_y_aprobacion(eid):
    # factura emitida pendiente de cobro: 1210,00 €, cliente BETA
    fac = client.post(
        f"/entidades/{eid}/facturas",
        json={
            "sentido": "devengado",
            "numero": "E-100",
            "proveedor": "CLIENTE BETA SA",
            "base_imponible": 1000.0,
            "iva": 210.0,
        },
    ).json()
    fid = fac["id"]

    extracto = _extracto_un_abono("00000000121000", "E-100", "CLIENTE BETA SA")
    prop = client.post(
        f"/entidades/{eid}/conciliacion", json={"formato": "n43", "contenido": extracto}
    )
    assert prop.status_code == 200
    data = prop.json()
    assert data["resumen_tiers"]["alta"] == 1
    assert data["avisos_cuadre"] == []  # el extracto cuadra
    match = data["propuesta"][0]
    assert match["tier"] == "alta"
    assert match["factura_id"] == fid
    exp_id = data["expediente_id"]
    assert data["status"] == "pending_approval"  # la IA NO marca cobrado sola

    # el HUMANO confirma el match → se marca la factura cobrada y se cierra
    apr = client.post(
        f"/entidades/{eid}/conciliacion/{exp_id}/aprobar",
        json={"matches": [{"movimiento_idx": 0, "factura_id": fid}]},
    ).json()
    assert apr["status"] == "closed"
    assert apr["matches_aplicados"] == [{"movimiento_idx": 0, "factura_id": fid}]
    assert apr["trazabilidad_integra"] is True

    # la factura quedó marcada cobrada, con traza inmutable
    det = client.get(f"/entidades/{eid}/expedientes/{fid}").json()
    assert det["expediente"]["data"]["cobrado"] is True
    assert "cobro_conciliado" in [e["kind"] for e in det["eventos"]]

    # re-conciliar el mismo abono ya no encuentra candidato (factura cobrada)
    prop2 = client.post(
        f"/entidades/{eid}/conciliacion", json={"formato": "n43", "contenido": extracto}
    ).json()
    assert prop2["resumen_tiers"]["abstencion"] == 1


def test_aprobar_aprende_alias_y_se_puede_auditar_y_revocar(eid):
    fac = client.post(
        f"/entidades/{eid}/facturas",
        json={
            "sentido": "devengado",
            "numero": "E-200",
            "proveedor": "GARCIA HERMANOS SL",
            "base_imponible": 1000.0,
            "iva": 210.0,
        },
    ).json()
    fid = fac["id"]
    extracto = _extracto_un_abono("00000000121000", "E-200", "GARCIA HERMANOS SL")
    exp_id = client.post(
        f"/entidades/{eid}/conciliacion", json={"formato": "n43", "contenido": extracto}
    ).json()["expediente_id"]

    apr = client.post(
        f"/entidades/{eid}/conciliacion/{exp_id}/aprobar",
        json={"matches": [{"movimiento_idx": 0, "factura_id": fid}]},
    ).json()
    assert apr["aliases_aprendidos"] == 1  # el flywheel aprendió de la confirmación humana

    # auditoría: el alias aparece y apunta a la contraparte de la factura
    aliases = client.get(f"/entidades/{eid}/aliases").json()
    assert aliases["count"] == 1
    alias = aliases["aliases"][0]
    assert alias["canonico"] == "GARCIA HERMANOS SL"
    assert "GARCIA" in alias["clave_tokens"]

    # revocación: queda fuera de los activos
    rev = client.post(f"/entidades/{eid}/aliases/{alias['id']}/revocar", json={})
    assert rev.status_code == 200
    assert client.get(f"/entidades/{eid}/aliases").json()["count"] == 0
    # revocar de nuevo → 404
    assert (
        client.post(f"/entidades/{eid}/aliases/{alias['id']}/revocar", json={}).status_code == 404
    )


def test_formato_no_soportado_da_400(eid):
    r = client.post(f"/entidades/{eid}/conciliacion", json={"formato": "ofx", "contenido": "x"})
    assert r.status_code == 400


def test_extracto_vacio_da_400(eid):
    r = client.post(f"/entidades/{eid}/conciliacion", json={"formato": "n43", "contenido": ""})
    assert r.status_code == 400
