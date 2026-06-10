"""
FUZZING / PROPERTY-BASED — en vez de casos a mano, MILES de inputs aleatorios comprobando INVARIANTES
que deben cumplirse SIEMPRE. Caza lo que no se me ocurre. Determinista por semilla; imprime el input
que viola la propiedad (reproducible). Uso: python scripts/fuzz_invariantes.py [--iters N]
"""

from __future__ import annotations

import argparse
import os
import random
import sys
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loombit_operator.agent.guardas import registro_guardas  # noqa: E402
from loombit_operator.agent.intencion import intencion_consecuente  # noqa: E402
from loombit_operator.agent.parsers import parsear_importe_es  # noqa: E402
from loombit_operator.skill_d_fiscal import guardas_fiscales as G  # noqa: E402,F401 (registra)
from loombit_operator.skill_d_fiscal.modelo_303 import LineaIVA, calcular_303  # noqa: E402
from loombit_operator.tools import dominio as Dm  # noqa: E402


def _fmt_es(x: float) -> str:
    """float → es-ES con 2 decimales y separador de miles ('1.234,56', '-200,00')."""
    s = f"{x:,.2f}"  # inglés: 1,234.56
    return s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--iters", type=int, default=3000)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    rnd = random.Random(args.seed)
    fallos: list[str] = []

    def viola(prop, detalle):
        fallos.append(f"[{prop}] {detalle}")

    # P1 · parsear_importe_es ROUND-TRIP: un importe es-ES único se recupera exacto.
    for _ in range(args.iters):
        cent = rnd.randint(-99_999_999, 99_999_999)
        x = round(cent / 100.0, 2)
        got = parsear_importe_es(f"reclama {_fmt_es(x)} € a un cliente")
        if got != x:
            viola("P1 round-trip", f"x={x} fmt={_fmt_es(x)!r} got={got!r}")

    # P2 · _variacion: el Δ recuperado == round(a-b,2) y el signo del % concuerda.
    for _ in range(args.iters):
        a = round(rnd.uniform(-1e6, 1e6), 2)
        b = round(rnd.uniform(-1e6, 1e6), 2)
        d_txt, pct = Dm._variacion(a, b)
        d_rec = float(d_txt.replace("+", "").replace(" €", ""))
        if d_rec != round(a - b, 2):
            viola("P2 Δ", f"a={a} b={b} d_txt={d_txt!r} esp={round(a - b, 2)}")
        if b != 0 and (a - b) < 0 and not pct.startswith("-"):
            viola("P2 signo%", f"a={a} b={b} pct={pct!r} (debería ser negativo)")
        if b != 0 and (a - b) > 0 and not pct.startswith("+"):
            viola("P2 signo%", f"a={a} b={b} pct={pct!r} (debería ser positivo)")

    # P3 · calcular_303: resultado == devengado − deducible, para CUALQUIER conjunto de líneas.
    tipos = [Decimal("0"), Decimal("0.04"), Decimal("0.05"), Decimal("0.10"), Decimal("0.21")]
    for _ in range(args.iters):
        lns = []
        for _ in range(rnd.randint(0, 5)):
            base = Decimal(str(round(rnd.uniform(-50000, 50000), 2)))
            lns.append(
                LineaIVA(
                    base=base,
                    tipo=rnd.choice(tipos),
                    sentido=rnd.choice(["devengado", "soportado"]),
                    concepto="x",
                )
            )
        r = calcular_303(lns)
        if r.resultado != (r.iva_devengado - r.iva_deducible):
            viola("P3 303", f"dev={r.iva_devengado} ded={r.iva_deducible} res={r.resultado}")

    # P4 · _periodos_comparados: el ANTERIOR termina antes que el ACTUAL, y la fecha cae en el ACTUAL.
    for _ in range(args.iters):
        from datetime import date

        y = rnd.randint(2000, 2099)
        m = rnd.randint(1, 12)
        d = date(y, m, rnd.randint(1, 28))
        for u in ("mes", "trimestre", "anio"):
            _, (da, ha, _), (db, hb, _) = Dm._periodos_comparados(u, d)
            if not (hb < da):
                viola("P4 orden", f"u={u} d={d} ha_ant={hb} >= da_act={da}")
            if not (da <= d <= ha):
                viola("P4 contiene", f"u={u} d={d} no en [{da},{ha}]")

    # P5 · CRASH/PUREZA: input unicode aleatorio nunca lanza, y es idempotente.
    for _ in range(args.iters):
        s = "".join(
            rnd.choice("€$%.,-−0123456789 abcñÑ¿?@\x00ＡＢ💰") for _ in range(rnd.randint(0, 40))
        )
        try:
            a1 = (
                parsear_importe_es(s),
                intencion_consecuente(s),
                bool(registro_guardas.aplicar(s)),
            )
            a2 = (
                parsear_importe_es(s),
                intencion_consecuente(s),
                bool(registro_guardas.aplicar(s)),
            )
            if a1 != a2:
                viola("P5 pureza", f"s={s!r} {a1} != {a2}")
        except Exception as exc:  # noqa: BLE001
            viola("P5 crash", f"s={s!r} → {exc!r}")

    print(f"  iters/prop: {args.iters} (seed {args.seed})")
    for f in fallos[:25]:
        print("  XX VIOLACIÓN " + f)
    print(f"\n== fuzzing: {len(fallos)} violaciones (deben ser 0) ==")
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
