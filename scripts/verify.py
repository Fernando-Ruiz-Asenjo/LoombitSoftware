"""
verify.py — la PUERTA de calidad de Loombit. Un solo comando que prueba el repo de verdad.

No se afirma "hecho" sin que esto pase. Lo usan:
- el hook de pre-commit (.githooks/pre-commit): BLOQUEA el commit si algo falla,
- CI (mismo conjunto de checks),
- yo, antes de decir que algo funciona.

Checks: formato (black) + lint (ruff) + tests (pytest, que incluyen el eval-set F1-F8).
Sale con código != 0 si cualquiera falla. Honesto: prueba que no hemos regresado, no "es perfecto".
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGETS = ["loombit_operator", "tests", "evals"]

CHECKS = [
    ("black (formato)", [sys.executable, "-m", "black", "--check", *TARGETS]),
    ("ruff (lint)", [sys.executable, "-m", "ruff", "check", *TARGETS]),
    ("pytest (tests + eval-set F1-F8)", [sys.executable, "-m", "pytest", "--no-cov", "-q"]),
]


def main() -> int:
    print("== Loombit · puerta de verificación ==")
    fallos = []
    for nombre, cmd in CHECKS:
        print(f"\n-> {nombre} ...")
        r = subprocess.run(cmd, cwd=ROOT)
        if r.returncode != 0:
            fallos.append(nombre)
            print(f"   FALLO: {nombre}")
        else:
            print(f"   OK: {nombre}")
    print("\n" + "=" * 50)
    if fallos:
        print("VERIFICACIÓN EN ROJO. No se da por hecho. Fallan: " + ", ".join(fallos))
        return 1
    print("VERIFICACIÓN VERDE. Tests + evals pasan; el comportamiento conocido no ha regresado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
