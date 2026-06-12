"""
CADENA DE GOBIERNO (D-79) — golden. El núcleo útil de «blockchain»: hash-chain tamper-evident.

Prueba: (1) la cadena REAL commiteada está íntegra; (2) una cadena bien formada verifica OK; (3) DIENTES —
editar, borrar, reordenar o romper un eslabón del pasado se CAZA. Sin red ni token; puro y determinista.
"""

from __future__ import annotations

import json

from scripts.auditoria_cadena import (
    CADENA,
    GENESIS_PREV,
    agregar,
    cargar,
    crear_genesis,
    hash_bloque,
    siguiente_bloque,
    verificar_cadena,
)

TS = "2026-06-12T00:00:00Z"


def _cadena_demo(n=3):
    bloques = [crear_genesis("demo", TS)]
    for i in range(1, n):
        bloques.append(siguiente_bloque(bloques[-1], "decision", f"D-{i}", {"n": i}, TS))
    return bloques


# ── 1) La cadena REAL del repo está íntegra ───────────────────────────────────


def test_cadena_real_integra():
    bloques = cargar(CADENA)
    assert bloques, "no hay cadena de gobierno commiteada"
    assert verificar_cadena(bloques) == []


# ── 2) Una cadena bien formada verifica OK ────────────────────────────────────


def test_cadena_bien_formada_ok():
    assert verificar_cadena(_cadena_demo(4)) == []


def test_genesis_prev_es_ceros():
    assert _cadena_demo(1)[0]["prev"] == GENESIS_PREV


def test_cada_prev_encadena_con_el_hash_anterior():
    b = _cadena_demo(3)
    assert b[1]["prev"] == b[0]["hash"]
    assert b[2]["prev"] == b[1]["hash"]


# ── 3) Dientes: manipular el pasado se caza ───────────────────────────────────


def test_editar_un_bloque_rompe_la_cadena():
    b = _cadena_demo(3)
    b[1]["datos"] = {"n": 999}  # alterar el contenido sin recomputar el hash
    errores = verificar_cadena(b)
    assert errores and any("hash no cuadra" in e for e in errores)


def test_editar_y_rehashear_sigue_roto_por_el_prev():
    # aunque el atacante recompute el hash del bloque editado, el SIGUIENTE prev ya no cuadra.
    b = _cadena_demo(3)
    b[1]["datos"] = {"n": 999}
    b[1]["hash"] = hash_bloque(b[1])  # re-sella el bloque editado
    errores = verificar_cadena(b)
    assert errores and any("prev roto" in e for e in errores)


def test_borrar_un_bloque_se_caza():
    b = _cadena_demo(4)
    del b[2]  # quitar uno del medio
    errores = verificar_cadena(b)
    assert errores  # seq no contiguo y/o prev roto


def test_reordenar_se_caza():
    b = _cadena_demo(4)
    b[1], b[2] = b[2], b[1]
    assert verificar_cadena(b)


def test_insertar_bloque_falso_se_caza():
    b = _cadena_demo(3)
    falso = siguiente_bloque(b[0], "decision", "FALSO", {"n": 42}, TS)
    b.insert(1, falso)  # inyectar entre génesis y el resto
    assert verificar_cadena(b)


# ── append persistente ────────────────────────────────────────────────────────


def test_agregar_persiste_y_encadena(tmp_path):
    p = tmp_path / "cadena.jsonl"
    agregar("decision", "D-X", {"a": 1}, TS, path=p)
    agregar("gate_verde", "ci-123", {"b": 2}, TS, path=p)
    bloques = cargar(p)
    assert len(bloques) == 3  # génesis + 2
    assert bloques[0]["tipo"] == "genesis"
    assert verificar_cadena(bloques) == []
    # y se persistió como JSON válido, una línea por bloque
    lineas = p.read_text(encoding="utf-8").strip().splitlines()
    assert len(lineas) == 3 and all(json.loads(ln) for ln in lineas)
