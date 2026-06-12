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
    # ── Mutantes de «Loombit Decide» + gobierno (prueban que LOS TESTS DE HOY tienen dientes) ──
    (
        "loombit_operator/ui_spec.py",
        "not _MARKUP.search(s)",
        "_MARKUP.search(s)",
        _pytest("test_", "tests/test_ui_spec.py"),
        "ui_spec: desactivar el filtro de inyección",
    ),
    (
        "loombit_operator/decisions.py",
        "if option_id not in {o.id for o in self.options}:",
        "if option_id in {o.id for o in self.options}:",
        _pytest("test_", "tests/test_decisions.py"),
        "decisions: aceptar una opción inexistente",
    ),
    (
        "loombit_operator/conducta.py",
        "and d <= a:",
        "and d >= a:",
        _pytest("test_", "tests/test_conducta.py"),
        "conducta: aceptar un prompt que NO mejora",
    ),
    (
        "loombit_operator/conducta.py",
        "elif v < VALOR_MIN:",
        "elif v > VALOR_MIN:",
        _pytest("test_", "tests/test_conducta.py"),
        "conducta: aceptar innovación de bajo valor",
    ),
    (
        "loombit_operator/autonomy.py",
        "if nivel_encola(level):",
        "if not nivel_encola(level):",
        _pytest("test_", "tests/test_autonomy.py"),
        "autonomy: invertir quién encola (observa actuaría)",
    ),
    (
        "loombit_operator/decisions_cobros.py",
        'if plan.get("action") != "reclamar":',
        'if plan.get("action") == "reclamar":',
        _pytest("test_", "tests/test_decisions_cobros.py"),
        "decisions_cobros: dejar de generar la decisión del cobro",
    ),
    # ── §14B-1: el guardia POST-LLM de cifras (que el hedge y el respaldo al céntimo tienen dientes) ──
    (
        "loombit_operator/agent/cifra_parser.py",
        "if c.aproximada:",
        "if not c.aproximada:",
        _pytest("test_", "tests/test_cifra_parser.py"),
        "cifra_parser: dejar pasar el '~2.400 €' narrado a ojo",
    ),
    (
        "loombit_operator/agent/cifra_parser.py",
        "abs(valor - r) <= TOL_CENTIMO",
        "abs(valor - r) >= TOL_CENTIMO",
        _pytest("test_", "tests/test_cifra_parser.py"),
        "cifra_parser: invertir el respaldo al céntimo",
    ),
    # ── Foso LOCAL (NORTE): que el detector de egress sin declarar tiene dientes ──
    (
        "scripts/auditoria_foso_local.py",
        "if clasificar(host) is None:",
        "if clasificar(host) is not None:",
        _pytest("test_", "tests/test_foso_local.py"),
        "foso_local: dejar pasar un egress NO declarado",
    ),
    # ── Cadena de gobierno (D-79): que el detector de manipulación tiene dientes ──
    (
        "scripts/auditoria_cadena.py",
        'if b.get("prev") != prev_hash:',
        'if b.get("prev") == prev_hash:',
        _pytest("test_", "tests/test_cadena.py"),
        "cadena: no detectar el eslabón roto (prev)",
    ),
    # ── La herramienta viva per-diff (D-80): que el check de tamaño tiene dientes ──
    (
        "scripts/auditoria_brujula.py",
        "if n > LIMITE_LINEAS",
        "if n < LIMITE_LINEAS",
        _pytest("test_", "tests/test_auditoria_brujula.py"),
        "brujula: dejar pasar un fichero > 400 líneas",
    ),
    # ── Check de PROMESA (D-82): que NO deja marcar 🟢 sin probar todos los criterios ──
    (
        "scripts/auditoria_promesas.py",
        'if estado == "🟢" and ref is None:',
        'if estado == "🟢" and ref is not None:',
        _pytest("test_", "tests/test_auditoria_promesas.py"),
        "promesas: dejar pasar un 🟢 con un criterio sin probar",
    ),
    # ── Intake de facturas (D-83): que la idempotencia tiene dientes ──
    (
        "loombit_operator/skill_d_fiscal/intake_batch.py",
        "if numero and numero in ya:",
        "if numero and numero not in ya:",
        _pytest("test_", "tests/test_intake_batch.py"),
        "intake: romper la idempotencia (re-procesa duplicados)",
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
