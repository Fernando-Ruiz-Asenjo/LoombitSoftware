"""
CUMPLIMIENTO DE LA BRÚJULA — el check que faltaba (§GOB-2 «la constitución COMPILA», D-68).

Hasta hoy, el verde de GitHub confirmaba el CÓDIGO (formato, tests, etc.) pero NUNCA que el agente aplicara
la constitución. Por eso se acumularon violaciones en verde (p.ej. 15 ficheros > 400 líneas). Este test
mecaniza las normas de la brújula que SÍ son comprobables por máquina, y corre en el gate: a partir de
ahora, el verde también exige cumplirlas.

Honestidad: esto NO comprueba la brújula "al completo" — normas como «mejora lo que se te pide» o
«cognición, no extracción» no son unit-testeables. Cubre las **mecanizables**; el residuo se declara.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "loombit_operator"

# ── Norma: ficheros < ~400 líneas (CLAUDE.md / BRÚJULA INGENIERÍA) ────────────────────────────────
# La realidad incumple en 15 ficheros. Se DECLARAN como deuda con su tamaño actual = techo: no pueden
# CRECER (ratchet a la baja, se arreglan dividiéndolos). Cualquier fichero FUERA de esta lista debe
# cumplir < 400. Así el verde caza un fichero nuevo gigante o uno existente que engorda. Bajar un techo
# (arreglar deuda) es libre; subirlo exige tocar esta lista a la vista de todos.
LIMITE = 400
_DEUDA_TAMANO = {
    "loombit_operator/agent/loop.py": 1433,
    "loombit_operator/agent/memory.py": 964,
    "loombit_operator/tools/dominio.py": 945,
    "loombit_operator/telar.py": 806,
    "loombit_operator/tools/pilot.py": 694,
    "loombit_operator/routers/computer.py": 673,
    "loombit_operator/skill_blanca_oauth.py": 550,
    "loombit_operator/pilot/windows_control.py": 537,
    "loombit_operator/routine_executors.py": 509,
    "loombit_operator/fabrica/chat.py": 492,
    "loombit_operator/tools/registry.py": 477,
    "loombit_operator/conciliacion.py": 445,
    "loombit_operator/tools/connectors.py": 443,
    "loombit_operator/fabrica/gepa.py": 416,
    "loombit_operator/comprension.py": 415,
}


def test_ningun_fichero_nuevo_supera_400_lineas():
    """Ficheros nuevos < 400; la deuda declarada no puede CRECER (ratchet)."""
    fallos = []
    for f in PKG.rglob("*.py"):
        rel = f.relative_to(ROOT).as_posix()
        n = len(f.read_text(encoding="utf-8").splitlines())
        techo = _DEUDA_TAMANO.get(rel, LIMITE)
        if n > techo:
            if rel in _DEUDA_TAMANO:
                fallos.append(f"{rel}: {n} > techo de deuda {techo} (un fichero en deuda ENGORDÓ)")
            else:
                fallos.append(f"{rel}: {n} > {LIMITE} (fichero nuevo demasiado grande; divídelo)")
    assert not fallos, "Violación de la norma <400 líneas:\n  " + "\n  ".join(fallos)


def test_la_deuda_de_tamano_solo_encoge():
    """Si arreglas un fichero en deuda (baja de su techo), actualiza la lista — para que el verde no
    permita que vuelva a crecer. Caza una lista de deuda mentirosa (techo muy por encima del real).
    """
    desfasados = []
    for rel, techo in _DEUDA_TAMANO.items():
        p = ROOT / rel
        if not p.exists():
            desfasados.append(f"{rel}: ya no existe; quítalo de la deuda")
            continue
        n = len(p.read_text(encoding="utf-8").splitlines())
        if n <= LIMITE:
            desfasados.append(f"{rel}: ya cumple ({n}<=400); sácalo de la deuda")
        elif n < techo - 20:  # margen: se encogió de verdad → baja el techo a la realidad
            desfasados.append(f"{rel}: ahora {n} (techo {techo}); baja el techo")
    assert not desfasados, "La deuda de tamaño está desfasada (ratchet):\n  " + "\n  ".join(
        desfasados
    )


# ── Norma §GOB-2: la tabla norma→mecanismo→auditoría no tiene celdas vacías ───────────────────────


def _filas_tabla_parte_iv() -> list[list[str]]:
    lineas = (ROOT / "docs" / "BRUJULA.md").read_text(encoding="utf-8").splitlines()
    filas, dentro = [], False
    for ln in lineas:
        if "Norma" in ln and "Mecanismo" in ln and ln.lstrip().startswith("|"):
            dentro = True
            continue
        if dentro:
            if not ln.lstrip().startswith("|"):
                break
            if set(ln.replace("|", "").strip()) <= {"-", ":", " "}:
                continue  # fila separadora
            celdas = [c.strip() for c in ln.strip().strip("|").split("|")]
            filas.append(celdas)
    return filas


def test_tabla_brujula_sin_celdas_vacias():
    """§GOB-2: ninguna fila con Mecanismo o Auditoría vacíos (norma decorativa = no entra)."""
    filas = _filas_tabla_parte_iv()
    assert len(filas) >= 8, f"la tabla Parte IV parece incompleta ({len(filas)} filas)"
    for celdas in filas:
        assert len(celdas) >= 3, f"fila mal formada: {celdas}"
        assert celdas[1], f"Mecanismo vacío en: {celdas[0]}"
        assert celdas[2], f"Auditoría vacía en: {celdas[0]}"


# ── Higiene de la bitácora y sincronía de la cabecera ─────────────────────────────────────────────


def test_decisiones_sin_duplicados():
    """Cada decisión, un D-NN único (una entrada por decisión)."""
    ids = re.findall(r"\*\*D-(\d+)", (ROOT / "docs" / "DECISIONES.md").read_text(encoding="utf-8"))
    dups = {x for x in ids if ids.count(x) > 1}
    assert not dups, f"D-NN duplicados en DECISIONES.md: {sorted(dups)}"


def test_claude_md_sincroniza_la_norma_canonica():
    """§META-3 / §GOB-2b: la cabecera (CLAUDE.md) refleja la norma canónica «hecho lo declara GitHub»."""
    claude = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "PROTOCOLO_VERIFICACION_CANONICO" in claude, "CLAUDE.md no apunta al protocolo canónico"
    assert "lo declara GitHub" in claude, "CLAUDE.md no refleja «hecho lo declara GitHub» (§GOB-2b)"
