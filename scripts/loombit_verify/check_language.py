#!/usr/bin/env python3
"""Gate anti teatro-de-verde: prohibe lenguaje de exito absoluto sin recibo.

Implementa el PASO D5 del ALGORITMO UNIFICADO.

Busca en documentos de estado / cuerpo de PR frases que declaran exito total
("0 bugs", "perfecto", "5-cero", "100% verde", ...). No prohibe el numero 100%
en general (la propia Brujula dice "al 100%"), solo las formulas que afirman
una perfeccion no verificable. El reporte honesto se hace con COBERTURA + lo
NO probado + recibo, no con superlativos.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

# Frases prohibidas (case-insensitive). Cada una afirma perfeccion/exito total.
BANNED = [
    r"\b0\s*bugs\b",
    r"\bcero\s*bugs\b",
    r"\bsin\s+bugs\b",
    r"\b0\s*fallos\b",
    r"\bcero\s*fallos\b",
    r"\bperfecto\b",
    r"\bperfecta\b",
    r"\b5[\s-]*cero\b",
    r"\b100\s*%\s*verde\b",
    r"\btodo\s+(en\s+)?verde\b",
    r"\b100\s*%\s*(probado|testeado|cubierto)\b",
    r"\bcobertura\s+(del\s+)?100\s*%\b",
    r"\bfunciona\s+de\s+maravilla\b",
]
PATTERNS = [re.compile(b, re.IGNORECASE) for b in BANNED]


def scan_text(text: str, label: str) -> list[str]:
    hits: list[str] = []
    for i, line in enumerate(text.splitlines(), 1):
        # Exencion explicita y visible en diff: una linea con 'verify-allow' se
        # salta (p.ej. el propio doc que DEFINE el vocabulario prohibido). Cada
        # exencion queda registrada linea a linea para que se revise.
        if "verify-allow" in line:
            continue
        for pat in PATTERNS:
            m = pat.search(line)
            if m:
                hits.append(f"ROJO  {label}:{i}: '{m.group(0)}' -> {line.strip()[:80]}")
    return hits


def check(paths: list[Path]) -> int:
    all_hits: list[str] = []
    for p in paths:
        files = sorted(p.rglob("*.md")) if p.is_dir() else [p]
        for f in files:
            if not f.exists():
                continue
            all_hits.extend(scan_text(f.read_text(encoding="utf-8"), str(f)))
    for h in all_hits:
        print(h)
    if all_hits:
        print(
            f"\nVEREDICTO: ROJO. {len(all_hits)} afirmacion(es) de exito absoluto sin recibo. "
            f"Reporta COBERTURA + lo NO probado + link al run."
        )
        return 1
    print("VEREDICTO: OK. Sin lenguaje de exito absoluto.")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Gate: prohibe lenguaje de exito absoluto.")
    p.add_argument("paths", nargs="+", type=Path, help="ficheros .md o directorios")
    args = p.parse_args(argv)
    return check(args.paths)


if __name__ == "__main__":
    raise SystemExit(main())
