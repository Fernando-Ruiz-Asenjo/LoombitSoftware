#!/usr/bin/env python3
"""Gate anti-tautologia: todo golden debe citar una FUENTE EXTERNA.

Implementa el PASO C1/D2 del ALGORITMO UNIFICADO.

Regla
-----
Un "golden" es un test que afirma un valor concreto (assert ... == <literal>).
El valor esperado de un golden NO puede salir del propio codigo que juzga; debe
venir de una fuente independiente (ley, spec, enunciado). Para probarlo, el
fichero de test debe declarar de donde sale el esperado con una marca:

    golden-source: Ley 37/1992 del IVA, art. 90

Si un fichero tiene aserciones golden pero NO cita fuente -> es un golden
tautologico (o sin oraculo) -> RECHAZADO. Esto caza la mentira que la mutacion
no ve: un test que afirma el literal correcto pero que nadie sabe de donde
salio (pudo copiarse de la salida del codigo).
"""

from __future__ import annotations

import argparse
import ast
import re
from pathlib import Path

MARKER = "golden-source:"
# El marcador cuenta como cita SOLO si va seguido de espacio(s) y una palabra
# real (letra/digito): `golden-source: Ley 37/1992`. Asi una MENCION en prosa
# como  'golden-source:'.  (comilla o puntuacion detras) NO cuenta como cita.
MARKER_RE = re.compile(r"golden-source:\s+\w", re.IGNORECASE)


def cita_fuente(source: str) -> bool:
    return bool(MARKER_RE.search(source))


def _is_literal(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float, str, bool)):
        return True
    # numeros negativos: -210.0
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return _is_literal(node.operand)
    return False


def has_golden_assertion(source: str) -> bool:
    """True si hay algun `assert <algo> ==/!= <literal>`."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Assert) and isinstance(node.test, ast.Compare):
            ops = node.test.ops
            comparators = node.test.comparators
            if ops and isinstance(ops[0], (ast.Eq, ast.NotEq)):
                if any(_is_literal(c) for c in comparators) or _is_literal(node.test.left):
                    return True
    return False


def iter_test_files(paths: list[Path]):
    for p in paths:
        if p.is_dir():
            yield from sorted(p.rglob("test_*.py"))
            yield from sorted(p.rglob("*_test.py"))
        elif p.name.startswith("test_") or p.name.endswith("_test.py"):
            yield p


def check(paths: list[Path]) -> int:
    violations: list[Path] = []
    checked = 0
    for f in iter_test_files(paths):
        source = f.read_text(encoding="utf-8")
        if has_golden_assertion(source):
            checked += 1
            if not cita_fuente(source):
                violations.append(f)
                print(f"ROJO  {f}: golden sin '{MARKER}' (esperado sin fuente externa citada)")
            else:
                print(f"ok    {f}: golden con fuente citada")
    if violations:
        print(
            f"\nVEREDICTO: ROJO. {len(violations)} golden(s) sin fuente externa. "
            f"Un esperado sin oraculo independiente puede ser tautologico -> RECHAZADO."
        )
        return 1
    print(f"\nVEREDICTO: OK. {checked} golden(s) revisados, todos citan fuente.")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Gate: golden debe citar fuente externa.")
    p.add_argument("paths", nargs="+", type=Path, help="ficheros o directorios de tests")
    args = p.parse_args(argv)
    return check(args.paths)


if __name__ == "__main__":
    raise SystemExit(main())
