"""Runner del eval-set — imprime el scorecard por taxonomía. Uso: `python -m evals.runner`.

Devuelve código de salida != 0 si algún eval determinista falla (apto para CI/pre-commit).
Los casos `needs_llm` solo corren con LOOMBIT_EVAL_LLM=1 (necesitan LM Studio).
"""

from __future__ import annotations

import os
import sys
from collections import defaultdict

from .cases import CASES
from .taxonomy import TAXONOMIA


def run() -> int:
    llm_on = os.environ.get("LOOMBIT_EVAL_LLM") == "1"
    por_taxon: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    fallos = 0

    for ev in CASES:
        if ev.check is None:
            estado, detalle = "PENDIENTE", "sin eval automatizado todavía"
        elif ev.needs_llm and not llm_on:
            estado, detalle = "SKIP", "necesita LM Studio (LOOMBIT_EVAL_LLM=1)"
        else:
            try:
                ok, detalle = ev.check()
                estado = "PASS" if ok else "FAIL"
                if not ok:
                    fallos += 1
            except Exception as exc:  # un eval que revienta cuenta como fallo
                estado, detalle = "ERROR", repr(exc)
                fallos += 1
        por_taxon[ev.taxon].append((ev.id, estado, detalle))

    print("\n=== SCORECARD DE EVALS (Loombit) ===\n")
    for taxon in sorted(TAXONOMIA):
        f = TAXONOMIA[taxon]
        print(f"[{taxon}] {f.descripcion}  (severidad: {f.severidad})")
        for cid, estado, detalle in por_taxon.get(taxon, []):
            print(f"    {estado:9} {cid:22} {detalle}")
        print()

    total = sum(1 for e in CASES if e.check is not None and not (e.needs_llm and not llm_on))
    print(f"Deterministas: {total - fallos}/{total} verdes · fallos: {fallos}")
    pend = [e.id for e in CASES if e.check is None]
    if pend:
        print(f"Huecos por cubrir (siguiente trabajo): {', '.join(pend)}")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(run())
