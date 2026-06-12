"""
auditoria_brujula.py — LA HERRAMIENTA VIVA: ¿aplicaste la brújula en ESTE cambio? (per-diff, D-80).

Las otras auditorías miran invariantes del repo entero; esta mira TU DIFF (lo que cambias vs `main`) y
DECIDE, binario, la parte MECÁNICA de la brújula. Lo que ninguna máquina puede juzgar (cognición, "acierta
al 100%", UX) NO se pinta de verde: se declara HUMANO; la conducta exige RECIBO (`conducta.py`). Tres cubos:

  🟥 ALGORITMO  → lo decide código (PASA/FALLA):
     · §INGENIERÍA   ningún fichero de producto tocado supera 400 líneas.
     · §META-3       si tocas la constitución (BRUJULA/CLAUDE) → exige entrada en DECISIONES.md.
     · §GOB-2        el diff NO introduce `--no-verify` (el gate no se salta).
     · §INGENIERÍA   un módulo de producto NUEVO trae su arnés (un test en el mismo diff).
  🟧 RECIBO     → conducta (Ley 0/innovación/veredicto): exige recibo cuantificable (`conducta.py`).
  ⬜ HUMANO     → cognición / acierta 100% / UX cálida: las revisa el subagente verificador + Fernando.

Frontera honesta: decide PROXIES mecánicos sobre el diff, no la calidad ni la intención. Determinista.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

LIMITE_LINEAS = 400
_CONSTITUCION = {"docs/BRUJULA.md", "CLAUDE.md"}
_PRODUCTO = "loombit_operator/"

# Lo que NO decide la máquina — se declara, no se finge (a la vista en cada corrida).
NO_MECANIZABLE = (
    "⬜ HUMANO: cognición · acierta al 100% · UX cálida → subagente verificador + Fernando.",
    "🟧 RECIBO: Ley 0 / innovación / veredicto → recibo cuantificable (loombit_operator/conducta.py).",
)


# ── Checks PUROS (sin git: testeables) ────────────────────────────────────────


def viola_tamano(archivos_lineas: list[tuple[str, int]]) -> list[str]:
    """§INGENIERÍA: ningún fichero de producto tocado supera el límite de líneas."""
    return [
        f"§INGENIERÍA: {f} tiene {n} líneas (> {LIMITE_LINEAS}); parte el dominio en skills/routers"
        for f, n in archivos_lineas
        if n > LIMITE_LINEAS
    ]


def viola_sync_constitucion(ficheros: set[str]) -> list[str]:
    """§META-3: tocar la constitución exige registrar la decisión en el mismo diff."""
    if (ficheros & _CONSTITUCION) and "docs/DECISIONES.md" not in ficheros:
        return ["§META-3: tocas la constitución (BRUJULA/CLAUDE) sin entrada en docs/DECISIONES.md"]
    return []


def viola_no_verify(lineas_anadidas: list[str]) -> list[str]:
    """§GOB-2: el diff no puede introducir un salto del gate."""
    if any("--no-verify" in ln for ln in lineas_anadidas):
        return ["§GOB-2: el diff introduce `--no-verify` (el gate canónico no se salta)"]
    return []


def viola_arnes(modulos_nuevos: list[str], hay_test_en_diff: bool) -> list[str]:
    """§INGENIERÍA: un módulo de producto NUEVO debe traer su arnés (un test) en el mismo cambio."""
    if modulos_nuevos and not hay_test_en_diff:
        return [
            f"§INGENIERÍA(arnés): módulo nuevo {m} sin ningún test en el diff (cada tarea trae su arnés)"
            for m in modulos_nuevos
        ]
    return []


# ── Fontanería de git (alimenta los checks puros) ─────────────────────────────


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


def _es_modulo_producto(f: str) -> bool:
    return f.startswith(_PRODUCTO) and f.endswith(".py") and not f.endswith("__init__.py")


def auditar_diff() -> tuple[list[str], bool]:
    """Devuelve (violaciones, tenia_contexto). Sin contexto git → no puede decidir (lo dice, no finge)."""
    base = _base()
    if base is None:
        return [], False
    cambiados = set((_git("diff", "--name-only", base, "HEAD") or "").split())
    cambiados |= set((_git("diff", "--name-only", "HEAD") or "").split())  # + sin commitear
    diff = _git("diff", base, "HEAD") or ""
    anadidas = [
        ln[1:] for ln in diff.splitlines() if ln.startswith("+") and not ln.startswith("+++")
    ]

    tamanos: list[tuple[str, int]] = []
    for f in cambiados:
        if _es_modulo_producto(f) and (ROOT / f).exists():
            tamanos.append((f, len((ROOT / f).read_text(encoding="utf-8").splitlines())))
    nuevos = [
        f
        for f in sorted(cambiados)
        if _es_modulo_producto(f) and _git("cat-file", "-e", f"{base}:{f}") is None
    ]
    hay_test = any(f.startswith("tests/") for f in cambiados)

    violaciones: list[str] = []
    violaciones += viola_tamano(tamanos)
    violaciones += viola_sync_constitucion(cambiados)
    violaciones += viola_no_verify(anadidas)
    violaciones += viola_arnes(nuevos, hay_test)
    return violaciones, True


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(
        description="¿Aplicaste la brújula en este diff? (per-diff)"
    ).parse_args(argv)
    violaciones, contexto = auditar_diff()
    for nota in NO_MECANIZABLE:
        print(f"  {nota}")
    if not contexto:
        print("== brújula per-diff: sin contexto git (no hay base vs main); nada que decidir ==")
        return 0
    if violaciones:
        print(
            f"== BRÚJULA per-diff ROJA: {len(violaciones)} norma(s) incumplida(s) en el cambio =="
        )
        for v in violaciones:
            print(f"  ❌ {v}")
        return 1
    print("== brújula per-diff VERDE: el cambio cumple la parte mecánica ==")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
