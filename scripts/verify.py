"""
verify.py — la PUERTA de calidad de Loombit. Un solo comando que prueba el repo de verdad.

§GOB-2: el gate canónico. Lo usan el hook de pre-commit, el CI y yo — **el mismo conjunto de checks**,
para que nada pase en un sitio y falle en otro (sin drift). No se afirma "hecho" sin que esto pase.

Dos niveles:
  - normal   → formato + lint + tests + auditorías deterministas + fuzz de invariantes.
  - --strict → además MUTATION TESTING (prueba que los tests tienen DIENTES, no son de mentira).

El **CI corre `--strict`** (la puerta del merge exige los dientes). El **hook** corre el nivel normal
(rápido, no muta ficheros). Honesto sobre lo que prueba: que el comportamiento conocido NO ha regresado,
que las cifras del camino crítico cumplen invariantes sobre miles de casos, y (en strict) que el arnés
caza bugs metidos a propósito. NO prueba "es perfecto" ni caza un 🟢 falso (eso es recibo + honestidad).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable

# black/ruff sobre TODO el repo, EXACTAMENTE como CI (§GOB-2, evita el drift que arregló PR #15).
_CORE = [
    ("black (formato)", [PY, "-m", "black", "--check", "."]),
    ("ruff (lint)", [PY, "-m", "ruff", "check", "."]),
    ("pytest (tests + eval-set F1-F8 + goldens)", [PY, "-m", "pytest", "--no-cov", "-q"]),
]

# Auditorías DETERMINISTAS (sin LLM, sin red, rápidas). Cada una sale != 0 si encuentra un hallazgo.
_AUDITS = [
    ("auditoría caja-blanca D1-D3 (449 sondas)", [PY, "scripts/auditoria_d1d2d3.py"]),
    (
        "auditoría del cobro (Ley 3/2004 + 5000 fuzz)",
        [PY, "scripts/auditoria_cobro.py", "--iters", "5000"],
    ),
    (
        "fuzz de invariantes (5000 casos/propiedad)",
        [PY, "scripts/fuzz_invariantes.py", "--iters", "5000"],
    ),
]

# Solo en --strict: muta el código a propósito y exige que el arnés se ponga ROJO (dientes).
_STRICT = [
    ("mutation testing (¿tienen dientes los tests?)", [PY, "scripts/mutation_test.py"]),
]


def _correr(checks: list[tuple[str, list[str]]], fallos: list[str]) -> None:
    for nombre, cmd in checks:
        print(f"\n-> {nombre} ...")
        r = subprocess.run(cmd, cwd=ROOT)
        if r.returncode != 0:
            fallos.append(nombre)
            print(f"   FALLO: {nombre}")
        else:
            print(f"   OK: {nombre}")


def main(argv: list[str] | None = None) -> int:
    strict = "--strict" in (argv if argv is not None else sys.argv[1:])
    print(f"== Loombit · puerta de verificación {'(STRICT)' if strict else ''} ==")
    fallos: list[str] = []
    _correr(_CORE, fallos)
    _correr(_AUDITS, fallos)
    if strict:
        _correr(_STRICT, fallos)
    print("\n" + "=" * 50)
    if fallos:
        print("VERIFICACIÓN EN ROJO. No se da por hecho. Fallan: " + ", ".join(fallos))
        return 1
    extra = " + dientes (mutación)" if strict else ""
    print(f"VERIFICACIÓN VERDE. Tests + auditorías + fuzz{extra}: el camino crítico aguanta.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
