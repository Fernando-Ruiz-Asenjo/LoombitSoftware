"""
Check de PROMESA (¿el código hace lo PEDIDO?) — golden con dientes.

Prueba que el motor confronta de verdad: una promesa sin criterios se rechaza, un criterio que nombra un
test inexistente se caza, y una promesa 🟢 con un criterio SIN test se caza (no puede ser "hecho" sin
probar todo). Y que el registro real `docs/PROMESAS.jsonl` está limpio. Determinista.
"""

from __future__ import annotations

from scripts.auditoria_promesas import (
    auditar,
    cargar,
    existe_test,
    validar_promesa,
)

PROMESA_OK = {
    "id": "demo",
    "pedido": "hacer X de verdad",
    "criterios": [
        {"que": "hace X", "test": "tests/test_auditoria_promesas.py::test_promesa_valida_pasa"}
    ],
    "estado": "🟢",
}


# ── Lo válido pasa ────────────────────────────────────────────────────────────


def test_promesa_valida_pasa():
    assert validar_promesa(PROMESA_OK) == []


def test_parcial_con_criterio_pendiente_es_valido():
    # una promesa 🟠 PUEDE tener un criterio aún sin test (pendiente, declarado).
    p = {"id": "p", "pedido": "algo", "criterios": [{"que": "pendiente"}], "estado": "🟠"}
    assert validar_promesa(p) == []


# ── Dientes: confronta de verdad ──────────────────────────────────────────────


def test_promesa_sin_criterios_falla():
    p = {"id": "p", "pedido": "algo", "criterios": [], "estado": "🟡"}
    assert validar_promesa(p) != []


def test_criterio_con_test_inexistente_falla():
    p = {
        "id": "p",
        "pedido": "algo",
        "criterios": [{"que": "x", "test": "tests/no_existe.py::test_fantasma"}],
        "estado": "🟠",
    }
    assert any("NO existe" in e for e in validar_promesa(p))


def test_verde_con_criterio_sin_test_falla():
    # 🟢 (hecho) pero un criterio no tiene prueba → no puede ser "hecho".
    p = {"id": "p", "pedido": "algo", "criterios": [{"que": "sin probar"}], "estado": "🟢"}
    assert any("SIN test" in e for e in validar_promesa(p))


def test_estado_invalido_falla():
    p = {"id": "p", "pedido": "x", "criterios": [{"que": "y"}], "estado": "verde"}
    assert validar_promesa(p) != []


# ── test_existe ───────────────────────────────────────────────────────────────


def test_existe_test_detecta_lo_real_y_lo_falso():
    assert existe_test("tests/test_auditoria_promesas.py::test_promesa_valida_pasa")
    assert not existe_test("tests/test_auditoria_promesas.py::test_que_no_existe")
    assert not existe_test("sin-doble-dos-puntos")


# ── El registro REAL del repo cumple ──────────────────────────────────────────


def test_registro_real_limpio():
    assert cargar(), "no hay ninguna promesa registrada"
    assert auditar() == []
