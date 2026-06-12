"""
INTEGRIDAD DEL GATE — el candado anti-debilitamiento (§GOB-2b / §GOB-3, D-67).

El agujero honesto del gate es que **el mismo agente que escribe el código escribe el gate**: en un PR
podría quitar un check, borrar tests o bajar un umbral y dejar el verde "barato". Este test no lo hace
imposible (también podría editarse este fichero), pero lo hace **RUIDOSO**: capar el gate pone ESTE test
en ROJO, y concentra la vigilancia humana en una superficie pequeña y con nombre — los ficheros del gate.

Si este test te obliga a actualizar un número, BIEN: bajar el listón debe ser un acto **deliberado y
visible**, no un descuido que pasa en verde. Subirlo (ratchet) es libre; bajarlo se nota.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERIFY = (ROOT / "scripts" / "verify.py").read_text(encoding="utf-8")
CI = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
PYPROJECT = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

# Suelos (RATCHET: solo se suben con un cambio deliberado y revisable; bajarlos pone este test en rojo).
MIN_TESTS = 830  # funciones `def test_` en tests/ (hoy ~834)
MIN_FUZZ_ITERS = 2000  # las auditorías de fuzz no pueden quedar en un puñado de casos
MIN_COV_FAIL_UNDER = 72  # el suelo de cobertura no puede desaparecer ni caer por debajo de esto

# Tests que NO pueden desaparecer (borrarlos = quitar un candado): nombre → marcadores que deben seguir ahí.
_CANDADOS_OBLIGATORIOS = {
    "tests/test_brujula_cumplimiento.py": ["_DEUDA_TAMANO", "test_tabla_brujula_sin_celdas_vacias"],
    "tests/test_gobierno_cobertura.py": [
        "MANIFIESTO",
        "test_toda_norma_de_la_brujula_esta_contabilizada",
    ],
    "tests/test_conducta.py": ["test_recibos_commiteados_son_validos", "BAJO VALOR"],
    "tests/test_gate_integridad.py": ["_CANDADOS_OBLIGATORIOS"],
}


def test_el_gate_corre_todos_los_checks():
    """verify.py debe seguir invocando TODAS las piezas del gate. Quitar una = este test rojo."""
    for pieza in (
        '"-m", "black"',
        '"-m", "ruff"',
        '"-m", "mypy"',
        '"-m", "pytest"',
        "auditoria_d1d2d3.py",
        "auditoria_cobro.py",
        "fuzz_invariantes.py",
        "mutation_test.py",
        "live_smoke.py",
    ):
        assert pieza in VERIFY, f"el gate ya no corre: {pieza} (¿se ha debilitado verify.py?)"


def test_la_mutacion_cubre_el_codigo_nuevo():
    """La mutación debe seguir probando los dientes del código de hoy (no se pueden quitar esos mutantes)."""
    mut = (ROOT / "scripts" / "mutation_test.py").read_text(encoding="utf-8")
    for modulo in (
        "ui_spec.py",
        "decisions.py",
        "conducta.py",
        "autonomy.py",
        "decisions_cobros.py",
        "cifra_parser.py",
    ):
        assert (
            modulo in mut
        ), f"la mutación ya no cubre {modulo} (¿se quitó el mutante con dientes?)"


def test_ci_corre_el_gate_estricto_y_en_vivo():
    """El CI debe correr el gate canónico en --strict --live (no una versión descafeinada)."""
    assert "scripts/verify.py --strict --live" in CI, "el CI ya no corre el gate --strict --live"


def test_no_se_borran_tests_en_masa():
    """Nº de funciones test >= suelo. Borrar tests para 'arreglar' algo pone esto en rojo."""
    total = 0
    for f in (ROOT / "tests").glob("*.py"):
        total += len(re.findall(r"^\s*def test_", f.read_text(encoding="utf-8"), re.MULTILINE))
    assert total >= MIN_TESTS, f"hay {total} tests (< suelo {MIN_TESTS}); ¿se han borrado tests?"


def test_no_se_bajan_los_iters_de_fuzz():
    """Las auditorías de fuzz mantienen un nº mínimo de casos (no se vacían a escondidas)."""
    for n in re.findall(r'"--iters",\s*"(\d+)"', VERIFY):
        assert int(n) >= MIN_FUZZ_ITERS, f"--iters {n} < suelo {MIN_FUZZ_ITERS} (fuzz debilitado)"


def test_los_candados_siguen_existiendo():
    """Los tests-candado (cumplimiento de brújula, integridad del gate) no pueden borrarse ni vaciarse:
    quitarlos = quitar una defensa, y eso debe ponerse ROJO aquí (blindaje del agujero 2)."""
    for rel, marcadores in _CANDADOS_OBLIGATORIOS.items():
        p = ROOT / rel
        assert p.exists(), f"falta el candado {rel} (¿se ha borrado una defensa del gate?)"
        txt = p.read_text(encoding="utf-8")
        for m in marcadores:
            assert m in txt, f"el candado {rel} ya no contiene «{m}» (¿se ha vaciado?)"


def test_existe_suelo_de_cobertura():
    """Debe existir un `fail_under` de cobertura y no estar por debajo del suelo (no se puede quitar)."""
    m = re.search(r"fail_under\s*=\s*(\d+)", PYPROJECT)
    assert (
        m
    ), "no hay `fail_under` de cobertura en pyproject.toml (el suelo de cobertura desapareció)"
    assert (
        int(m.group(1)) >= MIN_COV_FAIL_UNDER
    ), f"fail_under={m.group(1)} < suelo {MIN_COV_FAIL_UNDER} (cobertura debilitada)"
