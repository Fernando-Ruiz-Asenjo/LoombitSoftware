"""
Libro VeriFactu persistente (append-only, encadenado) — golden con dientes. Determinista.

Prueba lo que hace inalterable el libro en disco: cada alta encadena la huella del último guardado,
persiste entre instancias (releer no rompe la cadena), es idempotente por número, y una manipulación
del fichero se DETECTA (`verificar`) y bloquea seguir escribiendo (`CadenaCorrupta`).
"""

from __future__ import annotations

import json

from loombit_operator.docs_intel import InvoiceFields
from loombit_operator.skill_d_fiscal.verifactu import GENESIS
from loombit_operator.skill_d_fiscal.verifactu_store import (
    CadenaCorrupta,
    RegistroVerifactuStore,
)

NIF = "B12345678"


def _inv(numero, total=1210.0, fecha="2026-05-10"):
    return InvoiceFields(numero=numero, fecha=fecha, total=total, nif=NIF)


def test_alta_persiste_y_encadena(tmp_path):
    store = RegistroVerifactuStore(path=tmp_path / "vf.jsonl")
    r1, _ = store.registrar(_inv("F-1"), NIF)
    r2, _ = store.registrar(_inv("F-2"), NIF)
    assert r1 is not None and r2 is not None
    assert r1.huella_anterior == GENESIS  # primer eslabón
    assert r2.huella_anterior == r1.huella  # encadenado al anterior
    assert (tmp_path / "vf.jsonl").read_text(encoding="utf-8").count("\n") == 2  # append-only


def test_releer_no_rompe_la_cadena(tmp_path):
    p = tmp_path / "vf.jsonl"
    RegistroVerifactuStore(path=p).registrar(_inv("F-1"), NIF)
    # Nueva instancia: carga del disco y sigue encadenando sobre lo guardado.
    store2 = RegistroVerifactuStore(path=p)
    assert store2.verificar() == []  # lo cargado es íntegro
    r2, _ = store2.registrar(_inv("F-2"), NIF)
    assert r2 is not None and r2.huella_anterior == store2.list()[0].huella


def test_idempotente_por_numero(tmp_path):
    store = RegistroVerifactuStore(path=tmp_path / "vf.jsonl")
    store.registrar(_inv("F-1"), NIF)
    reg, avisos = store.registrar(_inv("F-1"), NIF)  # mismo número
    assert reg is None and avisos and "ya registrada" in avisos[0]
    assert len(store.list()) == 1  # no se duplica


def test_abstencion_si_faltan_campos(tmp_path):
    store = RegistroVerifactuStore(path=tmp_path / "vf.jsonl")
    reg, avisos = store.registrar(_inv("F-1", total=None), NIF)
    assert reg is None and avisos and "no se registra" in avisos[0]
    assert store.list() == []  # no entra al libro


def test_manipular_el_fichero_se_detecta_y_bloquea(tmp_path):
    p = tmp_path / "vf.jsonl"
    store = RegistroVerifactuStore(path=p)
    store.registrar(_inv("F-1", total=1210.0), NIF)
    store.registrar(_inv("F-2"), NIF)
    # Alterar a mano el importe del primer registro SIN recomputar su huella.
    lineas = p.read_text(encoding="utf-8").splitlines()
    d0 = json.loads(lineas[0])
    d0["importe_total"] = 9999.0
    lineas[0] = json.dumps(d0, ensure_ascii=False)
    p.write_text("\n".join(lineas) + "\n", encoding="utf-8")

    recargado = RegistroVerifactuStore(path=p)
    assert recargado.verificar()  # la manipulación se DETECTA
    try:
        recargado.registrar(_inv("F-3"), NIF)  # no se apila sobre un libro roto
        raise AssertionError("debería haber bloqueado")
    except CadenaCorrupta:
        pass
