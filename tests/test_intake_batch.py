"""
Intake de facturas (carpeta → cuentas a cobrar + 303) — golden de la PROMESA firmada (intake-facturas).

Un test por criterio del contrato (docs/PROMESAS.jsonl): carpeta entera, cuentas a cobrar, líneas de 303,
cifras por código, abstención honesta e idempotencia. Determinista; sin red ni LLM (la extracción es regex).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from loombit_operator.cuentas_cobrar import CuentasCobrarStore
from loombit_operator.expedientes import ExpedienteStore
from loombit_operator.skill_d_fiscal.intake_batch import intake_carpeta
from loombit_operator.skill_d_fiscal.verifactu_store import RegistroVerifactuStore

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
    exp = ExpedienteStore("test_intake", base_dir=tmp_path / "ent")
    cc = CuentasCobrarStore(path=tmp_path / "cc.json")
    return exp, cc


def _carpeta(tmp_path, **ficheros: str) -> Path:
    d = tmp_path / "facturas"
    d.mkdir()
    for nombre, contenido in ficheros.items():
        (d / nombre).write_text(contenido, encoding="utf-8")
    return d


# ── Criterio 1: la carpeta entera de golpe ────────────────────────────────────


def test_carpeta_entera_de_golpe(tmp_path, stores):
    exp, cc = stores
    carpeta = _carpeta(
        tmp_path, **{"f1.txt": FACTURA_1, "f2.txt": FACTURA_2, "basura.txt": ILEGIBLE}
    )
    r = intake_carpeta(carpeta, exp, cc)
    assert r.leidas == 2
    assert len(r.abstenidas) == 1


# ── Criterio 2: cuentas a cobrar ──────────────────────────────────────────────


def test_genera_cuentas_a_cobrar(tmp_path, stores):
    exp, cc = stores
    intake_carpeta(_carpeta(tmp_path, **{"f1.txt": FACTURA_1}), exp, cc)
    cuentas = cc.list()
    assert len(cuentas) == 1
    assert cuentas[0].cliente == "Cliente Uno SL"
    assert cuentas[0].vencimiento == "2026-06-09"


# ── Criterio 3: líneas de 303 ─────────────────────────────────────────────────


def test_genera_lineas_303(tmp_path, stores):
    exp, cc = stores
    r = intake_carpeta(_carpeta(tmp_path, **{"f1.txt": FACTURA_1, "f2.txt": FACTURA_2}), exp, cc)
    assert r.lineas_303 == 2


# ── Criterio 4: cifras por CÓDIGO (no el LLM) ─────────────────────────────────


def test_cifras_por_codigo_exactas(tmp_path, stores):
    exp, cc = stores
    intake_carpeta(_carpeta(tmp_path, **{"f1.txt": FACTURA_1}), exp, cc)
    # el importe es EXACTAMENTE el total parseado por regex determinista (1.210,00), no una estimación.
    assert cc.list()[0].importe == 1210.0


# ── Criterio 5: abstención honesta (no se inventa) ────────────────────────────


def test_abstencion_honesta(tmp_path, stores):
    exp, cc = stores
    r = intake_carpeta(_carpeta(tmp_path, **{"mala.txt": ILEGIBLE}), exp, cc)
    assert r.leidas == 0
    assert cc.list() == []  # NO inventa una cuenta
    assert r.abstenidas and "mala.txt" == r.abstenidas[0]["fichero"]
    assert "revísala" in r.abstenidas[0]["motivo"]


# ── Criterio 6: idempotente ───────────────────────────────────────────────────


def test_idempotente(tmp_path, stores):
    exp, cc = stores
    carpeta = _carpeta(tmp_path, **{"f1.txt": FACTURA_1, "f2.txt": FACTURA_2})
    intake_carpeta(carpeta, exp, cc)
    r2 = intake_carpeta(carpeta, exp, cc)  # segunda pasada
    assert r2.leidas == 0 and r2.duplicadas == 2
    assert len(cc.list()) == 2  # no se duplican las cuentas


# ── VeriFactu: las facturas EMITIDAS entran al libro encadenado ───────────────


def test_intake_alimenta_el_libro_verifactu(tmp_path, stores):
    exp, cc = stores
    vf = RegistroVerifactuStore(path=tmp_path / "vf.jsonl")
    carpeta = _carpeta(tmp_path, **{"f1.txt": FACTURA_1, "f2.txt": FACTURA_2})
    r = intake_carpeta(carpeta, exp, cc, store_vf=vf, nif_emisor="B12345678")
    assert r.registros_verifactu == 2
    regs = vf.list()
    assert regs[1].huella_anterior == regs[0].huella  # encadenados en el libro
    assert vf.verificar() == []  # íntegro
    # idempotente también en VeriFactu: re-procesar no duplica registros.
    intake_carpeta(carpeta, exp, cc, store_vf=vf, nif_emisor="B12345678")
    assert len(vf.list()) == 2


def test_sin_store_vf_no_registra_pero_sigue_el_intake(tmp_path, stores):
    exp, cc = stores
    r = intake_carpeta(_carpeta(tmp_path, **{"f1.txt": FACTURA_1}), exp, cc)
    assert r.registros_verifactu == 0 and r.leidas == 1  # opcional: sin store_vf no rompe nada


# ── Extra: lo no-factura se ignora ────────────────────────────────────────────


def test_ignora_lo_que_no_es_factura(tmp_path, stores):
    exp, cc = stores
    carpeta = _carpeta(tmp_path, **{"f1.txt": FACTURA_1, "notas.md": "hola", "imagen.png": "x"})
    r = intake_carpeta(carpeta, exp, cc)
    assert r.leidas == 1 and r.abstenidas == []
