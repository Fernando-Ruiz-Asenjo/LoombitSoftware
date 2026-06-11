"""
verify.py — la PUERTA de calidad de Loombit. Un solo comando que prueba el repo de verdad.

§GOB-2: el gate canónico. Lo usan el hook de pre-commit, el CI y yo — **el mismo conjunto de checks**,
para que nada pase en un sitio y falle en otro (sin drift). **"Hecho" NO es la palabra de nadie: es este
gate en verde, y GitHub CI lo re-confirma.** Ver `docs/PROTOCOLO_VERIFICACION_CANONICO.md`.

Niveles (acumulativos):
  - normal   → formato + lint + tests + auditorías deterministas + fuzz de invariantes.
  - --strict → además MUTATION TESTING (prueba que los tests tienen DIENTES, no son de mentira).
  - --live   → además TEST EN VIVO: arranca el servidor real y ejerce los endpoints por HTTP.

El **CI corre `--strict --live`** (la puerta del merge exige dientes + comportamiento en vivo). El **hook**
corre el nivel normal (rápido, no muta ficheros ni arranca el servidor). Honesto sobre lo que prueba: que el
comportamiento conocido NO ha regresado, que el camino crítico cumple invariantes sobre miles de casos, que
el arnés caza bugs metidos a propósito, y que el sistema CORRIENDO se comporta como se pide. NO prueba "es
perfecto" ni caza un 🟢 falso en una afirmación (por eso "hecho" lo declara el check, no el LLM).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable

# Módulos NUEVOS tipados (los typed por mí). El resto del repo arrastra el patrón `.list()` que tapa al
# builtin (AgentStore incl.) → type-check repo-wide es un refactor aparte, declarado, no fingido.
_MYPY_TARGETS = [
    "loombit_operator/conducta.py",
    "loombit_operator/ui_spec.py",
    "loombit_operator/autonomy.py",
    "loombit_operator/decisions_cobros.py",
    "loombit_operator/policy/authority_plane.py",
]

# black/ruff sobre TODO el repo, EXACTAMENTE como CI (§GOB-2, evita el drift que arregló PR #15).
_CORE = [
    ("black (formato)", [PY, "-m", "black", "--check", "."]),
    ("ruff (lint)", [PY, "-m", "ruff", "check", "."]),
    # mypy: type-check ESTRICTO de los módulos nuevos (caza una familia entera de bugs de tipo).
    (
        "mypy (tipos de los módulos nuevos)",
        [PY, "-m", "mypy", *_MYPY_TARGETS, "--ignore-missing-imports", "--follow-imports=silent"],
    ),
    # pytest CON cobertura: el `fail_under` de pyproject (§GOB-2b) pone el gate ROJO si la cobertura baja.
    ("pytest + cobertura (suelo fail_under)", [PY, "-m", "pytest", "-q"]),
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

# Solo en --live: arranca el servidor REAL y comprueba el comportamiento por HTTP (no mocks).
_LIVE = [
    ("test EN VIVO (servidor real, HTTP real)", [PY, "scripts/live_smoke.py"]),
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
    args = argv if argv is not None else sys.argv[1:]
    strict = "--strict" in args
    live = "--live" in args
    flags = " ".join(f for f in ("STRICT" if strict else "", "LIVE" if live else "") if f)
    print(f"== Loombit · puerta de verificación {('[' + flags + ']') if flags else ''} ==")
    fallos: list[str] = []
    _correr(_CORE, fallos)
    _correr(_AUDITS, fallos)
    if strict:
        _correr(_STRICT, fallos)
    if live:
        _correr(_LIVE, fallos)
    print("\n" + "=" * 50)
    if fallos:
        print("VERIFICACIÓN EN ROJO. No se da por hecho. Fallan: " + ", ".join(fallos))
        return 1
    extra = "".join([" + dientes (mutación)" if strict else "", " + EN VIVO" if live else ""])
    print(f"VERIFICACIÓN VERDE. Tests + auditorías + fuzz{extra}: el camino crítico aguanta.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# Prueba 2 del candado (no se funde).
