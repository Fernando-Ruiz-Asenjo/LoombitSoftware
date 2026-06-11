#!/usr/bin/env python3
"""Runner de mutación mínimo y autocontenido (solo stdlib).

Por qué existe
--------------
La verdad de una suite de tests no es "pasa en verde", sino "detecta un bug
cuando lo hay". Un test hueco (teatro de verde) pasa siempre pero no prueba
nada. Este runner lo destapa de forma automática: introduce un bug a propósito
en el código (un "mutante") y vuelve a correr los tests.

  - Si los tests SIGUEN EN VERDE con el bug dentro -> el mutante SOBREVIVIÓ ->
    la suite es hueca para ese punto. Es exactamente la mentira que buscamos.
  - Si los tests SE PONEN ROJOS -> el mutante fue MATADO -> la suite tiene
    poder real ahí.

mutation_score = mutantes_matados / mutantes_totales

El gate falla si el score < umbral. No depende de pytest: ejecuta el comando
de test que se le pase. Un mutante que CUELGA la suite (p.ej. `<` -> `>=` en
un bucle) cuenta como matado: el comportamiento cambió de forma detectable.

Implementa el PASO C/D del ALGORITMO DE GOBIERNO (docs/BRUJULA_ALGORITMO.md).
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tokenize
from dataclasses import dataclass
from io import StringIO
from pathlib import Path

# Operadores de mutación: cada uno transforma el código en algo "casi igual"
# pero con un bug. Un test que valide de verdad el comportamiento lo matará.
OP_MUTATIONS: dict[str, str] = {
    "+": "-",
    "-": "+",
    "*": "/",
    "/": "*",
    "==": "!=",
    "!=": "==",
    "<": ">=",
    ">": "<=",
    "<=": ">",
    ">=": "<",
}
NAME_MUTATIONS: dict[str, str] = {
    "and": "or",
    "or": "and",
    "True": "False",
    "False": "True",
}


@dataclass
class Mutant:
    line: int
    col: int
    original: str
    mutated: str
    source: str  # código fuente completo del mutante


def _replace_at(source: str, line: int, col: int, old: str, new: str) -> str:
    """Reemplaza `old` por `new` en la posición exacta (line/col, line 1-based)."""
    lines = source.splitlines(keepends=True)
    target = lines[line - 1]
    found = target[col : col + len(old)]
    assert found == old, f"desalineado en {line}:{col}: esperaba {old!r}, hay {found!r}"
    lines[line - 1] = target[:col] + new + target[col + len(old) :]
    return "".join(lines)


def generate_mutants(source: str) -> list[Mutant]:
    """Genera un mutante por cada operador mutable, ignorando strings y comentarios.

    Usa tokenize para no mutar dentro de literales/comentarios (eso daría
    falsos mutantes que no afectan al comportamiento).
    """
    mutants: list[Mutant] = []
    try:
        tokens = list(tokenize.generate_tokens(StringIO(source).readline))
    except tokenize.TokenError:
        return mutants

    for tok in tokens:
        text = tok.string
        if tok.type == tokenize.OP and text in OP_MUTATIONS:
            new = OP_MUTATIONS[text]
        elif tok.type == tokenize.NAME and text in NAME_MUTATIONS:
            new = NAME_MUTATIONS[text]
        else:
            continue
        line, col = tok.start
        mutated = _replace_at(source, line, col, text, new)
        mutants.append(Mutant(line=line, col=col, original=text, mutated=new, source=mutated))
    return mutants


def _clear_pycache(target: Path) -> None:
    """Borra __pycache__ cercanos: evita reusar bytecode de un mutante anterior.

    CRÍTICO: si Python carga un .pyc cacheado del fuente SIN mutar, el test
    pasa "en verde" con el bug dentro y el veredicto queda FALSEADO.
    """
    roots = {target.parent, Path.cwd()}
    for root in roots:
        for cache in root.rglob("__pycache__"):
            shutil.rmtree(cache, ignore_errors=True)


def _run(cmd: list[str], timeout: int) -> str:
    """Corre el comando y devuelve 'pass' | 'fail' | 'timeout'.

    PYTHONDONTWRITEBYTECODE=1: el subproceso NUNCA escribe .pyc, así que cada
    mutante se compila desde el fuente actual (no desde un caché obsoleto).
    """
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=timeout)
    except subprocess.TimeoutExpired:
        return "timeout"
    return "pass" if proc.returncode == 0 else "fail"


def run_mutation(target: Path, test_cmd: list[str], threshold: float, timeout: int) -> int:
    source = target.read_text(encoding="utf-8")
    _clear_pycache(target)  # arrancar sin bytecode cacheado

    # 1) Cordura: con el código ORIGINAL, los tests deben estar en verde.
    if _run(test_cmd, timeout) != "pass":
        print("ERROR: los tests fallan (o cuelgan) con el código original. Arregla eso primero.")
        return 2

    mutants = generate_mutants(source)
    if not mutants:
        print("ERROR: no se generaron mutantes (nada mutable). Gate no aplicable.")
        return 2

    killed = 0
    survivors: list[Mutant] = []
    original_bytes = target.read_bytes()
    try:
        for i, m in enumerate(mutants, 1):
            target.write_text(m.source, encoding="utf-8")
            result = _run(test_cmd, timeout)
            if result == "pass":
                # El bug NO rompió los tests -> sobrevivió -> suite hueca aquí.
                survivors.append(m)
                verdict = "SOBREVIVIO  (la suite NO lo caza)"
            else:
                killed += 1
                verdict = (
                    "matado" if result == "fail" else "matado (timeout: cambió el comportamiento)"
                )
            print(
                f"  [{i:>3}/{len(mutants)}] {target.name}:{m.line} "
                f"{m.original!r}->{m.mutated!r}  {verdict}"
            )
    finally:
        target.write_bytes(original_bytes)  # restaurar SIEMPRE el original
        _clear_pycache(target)

    score = killed / len(mutants)
    print()
    print(f"mutation_score = {killed}/{len(mutants)} = {score:.0%}  (umbral {threshold:.0%})")
    if survivors:
        print(f"MUTANTES SUPERVIVIENTES: {len(survivors)} -> la suite tiene huecos:")
        for m in survivors:
            print(f"    {target.name}:{m.line}  {m.original!r}->{m.mutated!r}")
    if score < threshold:
        print("VEREDICTO: ROJO. La suite es hueca (no detecta bugs). Claim 'verde' RECHAZADO.")
        return 1
    print("VEREDICTO: la suite tiene poder real. Gate de mutación superado.")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Gate de mutation testing (anti teatro-de-verde).")
    p.add_argument("target", type=Path, help="fichero .py a mutar")
    p.add_argument(
        "--test-cmd",
        required=True,
        help="comando que corre la suite (ej: 'python -m pytest tests/test_cobros.py --no-cov -q')",
    )
    p.add_argument("--threshold", type=float, default=0.8, help="score mínimo (0..1)")
    p.add_argument("--timeout", type=int, default=120, help="segundos por mutante (cuelgue=matado)")
    args = p.parse_args(argv)
    if not args.target.exists():
        print(f"ERROR: no existe {args.target}")
        return 2
    return run_mutation(args.target, args.test_cmd.split(), args.threshold, args.timeout)


if __name__ == "__main__":
    sys.exit(main())
