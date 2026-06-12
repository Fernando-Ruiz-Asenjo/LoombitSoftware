"""
La herramienta viva per-diff (D-80) — golden. ¿Decide bien la parte mecánica de la brújula sobre un cambio?

Prueba las funciones PURAS (sin git): cada check PASA con un diff limpio y FALLA con la violación que debe
cazar. Y que el auditor real corre sobre el repo sin reventar. Determinista.
"""

from __future__ import annotations

from scripts.auditoria_brujula import (
    LIMITE_LINEAS,
    NO_MECANIZABLE,
    auditar_diff,
    viola_arnes,
    viola_no_verify,
    viola_sync_constitucion,
    viola_tamano,
)

# ── §INGENIERÍA: tamaño ───────────────────────────────────────────────────────


def test_tamano_ok_bajo_limite():
    assert viola_tamano([("loombit_operator/x.py", LIMITE_LINEAS)]) == []


def test_tamano_falla_sobre_limite():
    v = viola_tamano([("loombit_operator/x.py", LIMITE_LINEAS + 1)])
    assert v and "§INGENIERÍA" in v[0]


# ── §META-3: sync constitución → DECISIONES ───────────────────────────────────


def test_constitucion_con_decisiones_ok():
    assert viola_sync_constitucion({"CLAUDE.md", "docs/DECISIONES.md"}) == []


def test_constitucion_sin_decisiones_falla():
    assert viola_sync_constitucion({"docs/BRUJULA.md"}) != []


def test_cambio_normal_no_exige_decisiones():
    # tocar código que NO es la constitución no dispara la regla.
    assert viola_sync_constitucion({"loombit_operator/x.py"}) == []


# ── §GOB-2: no --no-verify ────────────────────────────────────────────────────


def test_no_verify_detectado():
    assert viola_no_verify(["git commit --no-verify -m x"]) != []


def test_sin_no_verify_ok():
    assert viola_no_verify(["git commit -m x", "pytest -q"]) == []


# ── §INGENIERÍA: arnés del módulo nuevo ───────────────────────────────────────


def test_modulo_nuevo_sin_test_falla():
    assert viola_arnes(["loombit_operator/nuevo.py"], hay_test_en_diff=False) != []


def test_modulo_nuevo_con_test_ok():
    assert viola_arnes(["loombit_operator/nuevo.py"], hay_test_en_diff=True) == []


def test_sin_modulos_nuevos_ok():
    assert viola_arnes([], hay_test_en_diff=False) == []


# ── Lo no mecanizable se declara (no se finge verde) ──────────────────────────


def test_declara_lo_humano_y_el_recibo():
    blob = " ".join(NO_MECANIZABLE)
    assert "HUMANO" in blob and "RECIBO" in blob


# ── El auditor real corre sin reventar ────────────────────────────────────────


def test_auditar_diff_no_revienta():
    violaciones, contexto = auditar_diff()
    assert isinstance(violaciones, list) and isinstance(contexto, bool)
