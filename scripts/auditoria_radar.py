"""
auditoria_radar.py — EL RADAR VIVE, verificable: «si no hay radar, no pasa» (§INNOVACIÓN, D-85).

La brújula manda mantener un RADAR vivo: destilar tendencias y competidores REALES en propuestas concretas
para Loombit. Era una norma sin mecanismo (decoración). Esto la vuelve BINARIA: un registro
`docs/RADAR.jsonl` con señales reales —cada una con FUENTE (URL) y PROPUESTA accionable— y el gate se pone
ROJO si NO HAY radar (vacío/ausente/anémico) o si una señal es HUMO (sin fuente o sin propuesta).

No juzga si la idea es buena (eso es de Fernando); exige que la señal sea **real** (cita una fuente) y
**accionable** (trae una propuesta para Loombit) — mismo criterio que «un veredicto exige recibo de lectura».
Determinista, puro. La frescura («el radar se actualiza») la lleva una routine/humano (residuo declarado).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
RADAR = ROOT / "docs" / "RADAR.jsonl"

MIN_SENALES = 3  # un radar con menos de esto está anémico (no vive)
MIN_TEXTO = 15  # hallazgo/propuesta por debajo de esto es humo
_EVIDENCIA = {"dura", "blanda"}  # dura = dato/anuncio oficial; blanda = opinión/marketing
_REQUERIDOS = {"fecha", "tema", "fuente", "evidencia", "hallazgo", "propuesta"}


def cargar(path: Path = RADAR) -> list[dict[str, Any]]:
    """Lee el registro del radar (.jsonl). Lista vacía si no existe."""
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        if ln.strip():
            out.append(json.loads(ln))
    return out


def _texto_ok(x: Any) -> bool:
    return isinstance(x, str) and len(x.strip()) >= MIN_TEXTO


def validar_senal(s: Any) -> list[str]:
    """Una señal del radar: real (fuente URL) + accionable (propuesta). Devuelve sus fallos."""
    errores: list[str] = []
    if not isinstance(s, dict):
        return ["la señal debe ser un objeto"]
    tema = s.get("tema", "?")
    faltan = _REQUERIDOS - set(s)
    if faltan:
        errores.append(f"[{tema}] faltan campos {sorted(faltan)}")
    fuente = s.get("fuente")
    if not (isinstance(fuente, str) and fuente.startswith("http")):
        errores.append(f"[{tema}] sin FUENTE real (URL http): una señal sin fuente es humo")
    if s.get("evidencia") not in _EVIDENCIA:
        errores.append(f"[{tema}] «evidencia» debe ser «dura» o «blanda» (no afirmar sin marcar)")
    if not _texto_ok(s.get("hallazgo")):
        errores.append(f"[{tema}] «hallazgo» vacío o trivial")
    if not _texto_ok(s.get("propuesta")):
        errores.append(
            f"[{tema}] «propuesta» vacía: una señal sin propuesta para Loombit no cuenta"
        )
    return errores


def auditar(path: Path = RADAR) -> list[str]:
    """«Si no hay radar, no pasa.» Devuelve los fallos (vacía = el radar vive y es real)."""
    senales = cargar(path)
    if not senales:
        return ["NO HAY RADAR: `docs/RADAR.jsonl` ausente o vacío — el radar no vive (§INNOVACIÓN)"]
    fallos: list[str] = []
    if len(senales) < MIN_SENALES:
        fallos.append(
            f"radar ANÉMICO: {len(senales)} señal(es) < {MIN_SENALES} (no vive de verdad)"
        )
    for s in senales:
        fallos += validar_senal(s)
    return fallos


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description="¿Vive el radar? Si no hay radar, no pasa.").parse_args(
        argv
    )
    fallos = auditar()
    if fallos:
        print(f"== RADAR EN ROJO: {len(fallos)} fallo(s) — el radar no vive o trae humo ==")
        for f in fallos:
            print(f"  ❌ {f}")
        print(
            "  → mantén el radar vivo: señales reales (con fuente) y propuestas concretas para Loombit."
        )
        return 1
    senales = cargar()
    print(f"== el radar VIVE: {len(senales)} señales reales, cada una con fuente y propuesta ✅ ==")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
