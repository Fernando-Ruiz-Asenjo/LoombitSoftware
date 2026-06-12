"""
brujula_check.py — EL MOTOR QUE BLINDA: hace que las normas y el CLAUDE.md se APLIQUEN. Blanco, reutilizable.

«Si no aplica, no pasa.» Este check mira el DIFF de un cambio (vs `main`) y, si incumple la parte MECÁNICA
de las normas, sale en ROJO → con la rama protegida y este check como *required*, el PR NO se funde.

Honesto (lo mismo que en cualquier sitio): la máquina solo puede APLICAR lo mecánico. Lo de juicio
(¿se entendió el problema?, ¿la UX es buena?) NO se finge de verde: se DECLARA para revisión humana.

  🟥 BLOQUEA (mecánico, sobre el diff):
     · ningún fichero de código tocado supera el límite de líneas
     · un módulo de código NUEVO trae su test (arnés)
     · tocar la constitución (CLAUDE/normas) exige una entrada en el registro de decisiones
     · el diff no introduce un salto del gate (`--no-verify`)
  ⬜ DECLARA (no mecanizable): juicio/conducta → revisión humana / recibo.

CÓMO ADOPTARLO: copia este fichero a tu repo, AJUSTA el bloque CONFIG, súmalo al CI y hazlo *required*
en la protección de rama. A partir de ahí, las normas se aplican solas.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

# ── CONFIG — AJUSTA esto a tu proyecto (lo único que se toca al adoptarlo) ─────────────────────────
CODE_DIRS: tuple[str, ...] = ("src/",)  # carpetas con el código de producto
TEST_DIR = "tests/"  # donde viven los tests (los arneses)
LIMITE_LINEAS = 400  # tamaño máximo por fichero
CONSTITUCION = {"CLAUDE.md", "BRUJULA.md"}  # ficheros de normas que exigen registrar la decisión
DECISIONES = "DECISIONES.md"  # el registro de decisiones
# ───────────────────────────────────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent

NO_MECANIZABLE = (
    "⬜ HUMANO: ¿se entendió el problema? · ¿la UX es buena? → revisión humana, no se finge de verde.",
    "🟧 RECIBO: mejoras / veredictos → evidencia cuantificable, o no cuentan.",
)


# ── Checks PUROS (sin git: testeables y con dientes) ──────────────────────────


def viola_tamano(archivos_lineas: list[tuple[str, int]]) -> list[str]:
    """Ningún fichero de código tocado supera el límite."""
    return [
        f"TAMAÑO: {f} tiene {n} líneas (> {LIMITE_LINEAS}); pártelo."
        for f, n in archivos_lineas
        if n > LIMITE_LINEAS
    ]


def viola_sync_constitucion(ficheros: set[str]) -> list[str]:
    """Tocar la constitución exige registrar la decisión en el mismo cambio."""
    if (ficheros & CONSTITUCION) and DECISIONES not in ficheros:
        return [
            f"NORMAS: tocas la constitución sin entrada en {DECISIONES} (cambio de norma sin registro)"
        ]
    return []


def viola_no_verify(lineas_anadidas: list[str]) -> list[str]:
    """El diff no puede introducir un salto del gate."""
    if any("--no-verify" in ln for ln in lineas_anadidas):
        return ["GATE: el diff introduce `--no-verify` (el gate no se salta)"]
    return []


def viola_arnes(modulos_nuevos: list[str], hay_test_en_diff: bool) -> list[str]:
    """Un módulo de código NUEVO debe traer su arnés (un test) en el mismo cambio."""
    if modulos_nuevos and not hay_test_en_diff:
        return [f"ARNÉS: módulo nuevo {m} sin ningún test en el diff" for m in modulos_nuevos]
    return []


# ── Fontanería de git ─────────────────────────────────────────────────────────


def _git(*args: str) -> str | None:
    try:
        r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    except FileNotFoundError:
        return None
    return r.stdout if r.returncode == 0 else None


def _base() -> str | None:
    for ref in ("origin/main", "main"):
        if _git("rev-parse", "--verify", "--quiet", ref) is not None:
            mb = _git("merge-base", ref, "HEAD")
            if mb and mb.strip():
                return mb.strip()
    return None


def _es_codigo(f: str) -> bool:
    return (
        f.endswith(".py")
        and not f.endswith("__init__.py")
        and any(f.startswith(d) for d in CODE_DIRS)
    )


def auditar_diff() -> tuple[list[str], bool]:
    """(violaciones, hubo_contexto). Sin contexto git → lo DICE, no finge verde."""
    base = _base()
    if base is None:
        return [], False
    cambiados = set((_git("diff", "--name-only", base, "HEAD") or "").split())
    cambiados |= set((_git("diff", "--name-only", "HEAD") or "").split())
    diff = _git("diff", base, "HEAD") or ""
    anadidas = [
        ln[1:] for ln in diff.splitlines() if ln.startswith("+") and not ln.startswith("+++")
    ]

    tamanos = [
        (f, len((ROOT / f).read_text(encoding="utf-8").splitlines()))
        for f in cambiados
        if _es_codigo(f) and (ROOT / f).exists()
    ]
    nuevos = [
        f
        for f in sorted(cambiados)
        if _es_codigo(f) and _git("cat-file", "-e", f"{base}:{f}") is None
    ]
    hay_test = any(f.startswith(TEST_DIR) for f in cambiados)

    v: list[str] = []
    v += viola_tamano(tamanos)
    v += viola_sync_constitucion(cambiados)
    v += viola_no_verify(anadidas)
    v += viola_arnes(nuevos, hay_test)
    return v, True


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(
        description="¿Se aplicó la brújula en este cambio? Si no, falla."
    ).parse_args(argv)
    violaciones, contexto = auditar_diff()
    for nota in NO_MECANIZABLE:
        print(f"  {nota}")
    if not contexto:
        print("== brújula: sin contexto git (base vs main); nada que aplicar ==")
        return 0
    if violaciones:
        print(f"== NO PASA: {len(violaciones)} norma(s) sin aplicar en el cambio ==")
        for x in violaciones:
            print(f"  ❌ {x}")
        return 1
    print("== brújula aplicada: el cambio cumple la parte mecánica ✅ ==")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
