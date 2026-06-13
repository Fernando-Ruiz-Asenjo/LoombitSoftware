"""
INTAKE F-5 (carpeta → facturas + cuentas + 303 de un tirón) + F-6 (abstención honesta "conéctalas").

Golden determinista, sin red ni LLM (la extracción es regex; las cifras, por código). F-5 verifica que
`intake_y_liquidar` encadena el poblado de la plataforma y la liquidación del 303 con cifras EXACTAS y
abstención honesta de lo ilegible. F-6 verifica que `GET /cuentas`, con el store VACÍO, guía a conectar
las facturas (`sin_datos` + mensaje) en vez de devolver un vacío mudo; con datos, no lo marca.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from loombit_operator.cuentas_cobrar import CuentaCobrar, CuentasCobrarStore
from loombit_operator.expedientes import ExpedienteStore
from loombit_operator.main import app
from loombit_operator.routers import cuentas as cuentas_router
from loombit_operator.skill_d_fiscal.intake_batch import intake_y_liquidar

client = TestClient(app)

FACTURA_1 = """Cliente Uno SL
NIF: B12345678
Factura nº F-2026-001
Fecha de factura: 2026-05-10
Vencimiento: 2026-06-09
Base imponible: 1.000,00 EUR
IVA: 210,00 EUR
Total a pagar: 1.210,00 EUR"""

FACTURA_2 = """Cliente Dos SL
NIF: B87654321
Factura nº F-2026-002
Fecha de factura: 2026-05-15
Vencimiento: 2026-06-14
Base imponible: 2.000,00 EUR
IVA: 420,00 EUR
Total a pagar: 2.420,00 EUR"""

ILEGIBLE = "una nota cualquiera sin número, sin nif, sin total"


@pytest.fixture()
def stores(tmp_path):
    exp = ExpedienteStore("test_f5", base_dir=tmp_path / "ent")
    cc = CuentasCobrarStore(path=tmp_path / "cc.json")
    return exp, cc


def _carpeta(tmp_path, **ficheros: str) -> Path:
    d = tmp_path / "facturas"
    d.mkdir()
    for nombre, contenido in ficheros.items():
        (d / nombre).write_text(contenido, encoding="utf-8")
    return d


# ── F-5: la carpeta entera → cuentas + 303, de un tirón ───────────────────────


def test_f5_intake_y_303_de_un_tiron(tmp_path, stores):
    exp, cc = stores
    carpeta = _carpeta(tmp_path, **{"f1.txt": FACTURA_1, "f2.txt": FACTURA_2})
    r = intake_y_liquidar(carpeta, exp, cc, "2T 2026")
    # Plataforma poblada: 2 facturas leídas → 2 cuentas a cobrar + 2 líneas de 303.
    assert r["intake"]["leidas"] == 2
    assert r["intake"]["cuentas_creadas"] == 2
    assert r["intake"]["lineas_303"] == 2
    # 303: IVA devengado 210 + 420 = 630, deducible 0 → resultado a pagar 630,00 (cifra por CÓDIGO).
    assert float(r["303"]["resultado"]) == 630.0
    # La IA NO presenta: el 303 queda pendiente de aprobación humana.
    assert r["303"]["status"] == "pending_approval"
    assert cc.list()[0].importe == 1210.0  # importe exacto parseado, no estimado


def test_f5_abstencion_honesta_no_inventa(tmp_path, stores):
    exp, cc = stores
    r = intake_y_liquidar(_carpeta(tmp_path, **{"mala.txt": ILEGIBLE}), exp, cc, "2T 2026")
    assert r["intake"]["leidas"] == 0
    assert cc.list() == []  # no inventa una cuenta
    assert r["intake"]["abstenidas"] and r["intake"]["abstenidas"][0]["fichero"] == "mala.txt"
    assert float(r["303"]["resultado"]) == 0.0  # sin facturas legibles → 303 a cero, no inventado


# ── F-6: GET /cuentas con el store vacío guía a conectar (no un vacío mudo) ────


@pytest.fixture()
def store_aislado(tmp_path, monkeypatch):
    path = tmp_path / "cuentas_cobrar.json"
    monkeypatch.setattr(cuentas_router, "CuentasCobrarStore", lambda: CuentasCobrarStore(path=path))
    return path


def test_f6_cuentas_vacias_guian_a_conectar(store_aislado):
    data = client.get("/cuentas").json()
    assert data["sin_datos"] is True
    assert "factura" in data["mensaje"].lower() and "303" in data["mensaje"]
    assert data["pendientes"] == [] and data["total_pendiente"] == 0


def test_f6_con_cuentas_no_marca_sin_datos(store_aislado):
    CuentasCobrarStore(path=store_aislado).add(
        CuentaCobrar(cliente="Acme SL", importe=500.0, vencimiento="2026-06-01")
    )
    data = client.get("/cuentas").json()
    assert not data.get("sin_datos")
    assert "mensaje" not in data
