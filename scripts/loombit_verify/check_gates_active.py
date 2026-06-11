#!/usr/bin/env python3
"""Meta-gate: vigila que NADIE haya apagado los gates (vigilar al vigilante).

Verifica que el workflow de CI sigue invocando cada gate obligatorio y que
ninguno está comentado o saltado. Si el agente intenta debilitar su propia
jaula, esto se pone ROJO. Atado a CODEOWNERS: cambiar los ficheros del
verificador exige revisión humana; este check además detecta el apagado
silencioso (if: false, continue-on-error: true, gate comentado).
"""

from __future__ import annotations

import sys
from pathlib import Path

WORKFLOW = Path(".github/workflows/loombit-verify.yml")

# Cada gate obligatorio debe aparecer invocado en el workflow.
REQUIRED = [
    "check_golden_source.py",
    "check_language.py",
    "mutation.py",
    "test_loombit_verify.py",
    "check_gates_active.py",  # el meta-gate se vigila a sí mismo
]
# Señales de apagado: si aparecen en el workflow, sospechoso.
DISABLED_MARKERS = ["if: false", "continue-on-error: true", "# DISABLED"]


def check() -> int:
    if not WORKFLOW.exists():
        print(f"ROJO: no existe {WORKFLOW}. El sistema de verificación no está cableado en CI.")
        return 1
    text = WORKFLOW.read_text(encoding="utf-8")
    problems: list[str] = []

    for gate in REQUIRED:
        # debe aparecer en una línea no comentada
        active = any(gate in ln and not ln.strip().startswith("#") for ln in text.splitlines())
        if not active:
            problems.append(f"gate ausente o comentado: {gate}")

    for marker in DISABLED_MARKERS:
        if marker in text:
            problems.append(f"marca de apagado encontrada en el workflow: '{marker}'")

    if problems:
        print("VEREDICTO: ROJO. Alguien debilitó la jaula de verificación:")
        for p in problems:
            print(f"    - {p}")
        return 1
    print(f"VEREDICTO: OK. {len(REQUIRED)} gates activos y sin marcas de apagado.")
    return 0


if __name__ == "__main__":
    sys.exit(check())
