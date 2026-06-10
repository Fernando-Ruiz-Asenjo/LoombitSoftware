"""
MUTATION TESTING — ¿tiene DIENTES el arnés? Para cada mutación (un bug introducido a propósito en una
función crítica), aplica el cambio, corre el chequeo correspondiente y verifica que se pone ROJO. Si
una mutación SOBREVIVE (el chequeo sigue verde), ese camino NO está cubierto → hay que añadir un test.

SIEMPRE restaura el fichero (try/finally), incluso si algo falla. Uso: python scripts/mutation_test.py
"""

from __future__ import annotations

import os
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# chequeos: 'audit' = la auditoría determinista (rápida, <1s); 'pytest:K' = pytest -k K (más lento).
_AUDIT = [sys.executable, os.path.join("scripts", "auditoria_d1d2d3.py")]


def _pytest(k, fichero):
    return [sys.executable, "-m", "pytest", fichero, "-q", "-o", "addopts=", "-k", k]


# (fichero relativo, buscar, reemplazar, chequeo, etiqueta) — cada uno DEBE ponerse rojo.
MUTACIONES = [
    (
        "loombit_operator/agent/parsers.py",
        "mill[oó]n(?:es)?|k)",
        "mill[oó]n(?:es)?)",
        _AUDIT,
        "parser: quitar escala 'k'",
    ),
    (
        "loombit_operator/agent/parsers.py",
        "len(distintos) == 1",
        "len(distintos) >= 1",
        _AUDIT,
        "parser: multi-importe deja de ser None",
    ),
    (
        "loombit_operator/skill_d_fiscal/guardas_fiscales.py",
        "facturar[eé]|ingresar[eé]|vender[eé]|cobrar[eé]",
        "ingresar[eé]|vender[eé]|cobrar[eé]",
        _AUDIT,
        "guarda: quitar predicción 'facturaré'",
    ),
    (
        "loombit_operator/skill_d_fiscal/guardas_fiscales.py",
        "(100|111|115",
        "(111|115",
        _AUDIT,
        "guarda: quitar modelo 100",
    ),
    (
        "loombit_operator/skill_d_fiscal/guardas_fiscales.py",
        "|cruz\\w+)",
        ")",
        _AUDIT,
        "guarda: quitar conciliación 'cruz'",
    ),
    (
        "loombit_operator/tools/dominio.py",
        "delta = round(actual - anterior, 2)",
        "delta = round(actual + anterior, 2)",
        _AUDIT,
        "comparativo: variación con SIGNO MAL",
    ),
    (
        "loombit_operator/agent/loop.py",
        "round(imp / (1.0 + tf), 2)",
        "round(imp * (1.0 + tf), 2)",
        _pytest("importe", "tests/test_cerebro_golden.py"),
        "corrector: IVA-incluido al revés",
    ),
    (
        "loombit_operator/skill_d_fiscal/modelo_303.py",
        "(devengado - deducible).quantize(CENT)",
        "(devengado + deducible).quantize(CENT)",
        _pytest("303 or rectificativa or registradas", "tests/test_dominio_tools.py"),
        "303: resultado SUMA en vez de RESTA",
    ),
]


# Sin escribir .pyc: si no, el subprocess deja bytecode rancio de la versión mutada y el restore del
# .py no lo invalida (colisión de mtime) → el siguiente run usa el bug ya «revertido». I/O en BINARIO
# para preservar EXACTOS los bytes (line-endings/encoding) y no ensuciar el árbol.
_ENV = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}


def main() -> int:
    cazadas = sobrevividas = 0
    for rel, buscar, reemplazar, chequeo, etq in MUTACIONES:
        ruta = os.path.join(RAIZ, rel)
        with open(ruta, "rb") as f:
            orig = f.read()
        bb, br = buscar.encode("utf-8"), reemplazar.encode("utf-8")
        if bb not in orig:
            print(f"  ?? NO-APLICA  {etq}  (no encontré: {buscar!r})")
            continue
        if orig.count(bb) != 1:
            print(f"  ?? AMBIGUA    {etq}  ({orig.count(bb)} apariciones de {buscar!r})")
            continue
        try:
            with open(ruta, "wb") as f:
                f.write(orig.replace(bb, br, 1))
            r = subprocess.run(
                chequeo,
                cwd=RAIZ,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=_ENV,
            )
            rojo = r.returncode != 0  # el chequeo FALLÓ → la mutación fue CAZADA
        finally:
            with open(ruta, "wb") as f:
                f.write(orig)  # restaurar SIEMPRE (bytes exactos)
        if rojo:
            cazadas += 1
            print(f"  ✅ CAZADA     {etq}")
        else:
            sobrevividas += 1
            print(f"  ❌ SOBREVIVE  {etq}  ← HUECO: el arnés NO lo detecta")
    print(f"\n== mutaciones: {cazadas} cazadas · {sobrevividas} SOBREVIVEN (deben ser 0) ==")
    return 1 if sobrevividas else 0


if __name__ == "__main__":
    raise SystemExit(main())
