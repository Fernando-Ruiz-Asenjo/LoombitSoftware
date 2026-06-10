"""
AUDITORÍA del CÁLCULO DEL COBRO (Ley 3/2004) — tan dura como la del 303. Casos a mano (fronteras de
etapa, interés de demora, saldo) con valores calculados a mano + INVARIANTES sobre miles de casos
aleatorios. Uso: python scripts/auditoria_cobro.py [--iters N]
"""

from __future__ import annotations

import argparse
import os
import random
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loombit_operator.cobros import (  # noqa: E402
    LATE_FEE_FIXED_EUR,
    dunning_plan,
    escalation_stage,
    late_interest,
)

_HOY = date(2026, 6, 15)
fallos: list[str] = []


def chk(lbl, got, exp):
    if got != exp:
        fallos.append(f"{lbl}: got={got!r} exp={exp!r}")


def _venc(overdue: int) -> str:
    return (_HOY - timedelta(days=overdue)).isoformat()


# ── Fronteras de ETAPA (calculadas a mano) ──
for ov, et in [
    (-1, "por_vencer"),
    (0, "vence_hoy"),
    (1, "recordatorio_amistoso"),
    (7, "recordatorio_amistoso"),
    (8, "recordatorio_firme"),
    (21, "recordatorio_firme"),
    (22, "reclamacion_formal"),
    (60, "reclamacion_formal"),
    (61, "via_judicial"),
    (365, "via_judicial"),
]:
    chk(f"etapa overdue={ov}", escalation_stage(ov), et)

# ── INTERÉS de demora (a mano) ──
chk("interés 1000 @8% 365d", late_interest(1000, 365, 8.0)["amount"], 80.0)  # 1000*0.08*1
chk("interés 1000 @8% 30d", late_interest(1000, 30, 8.0)["amount"], 6.58)  # 2400/365=6.5753
chk("interés overdue 0 → 0", late_interest(1000, 0, 8.0)["amount"], 0.0)
chk("interés overdue -5 → 0", late_interest(1000, -5, 8.0)["amount"], 0.0)
chk("interés principal 0 → 0", late_interest(0, 30, 8.0)["amount"], 0.0)
chk("interés sin tipo → rate_required", late_interest(1000, 30, None)["rate_required"], True)

# ── dunning_plan (a mano) ──
p = dunning_plan(
    total=1000, due_date=_venc(30), today=_HOY.isoformat(), paid=400, annual_rate_pct=8.0
)
chk("dunning saldo parcial", p["outstanding"], 600.0)
chk("dunning etapa 30d", p["stage"], "reclamacion_formal")
chk("dunning compensación art.8", p["fixed_compensation_eur"], LATE_FEE_FIXED_EUR)
chk("dunning interés sobre saldo", p["interest"]["amount"], 3.95)  # 600*0.08*30/365=1440/365
p2 = dunning_plan(total=1000, due_date=_venc(30), today=_HOY.isoformat(), paid=1000)
chk("dunning cobrada → cobrado", p2["stage"], "cobrado")
p3 = dunning_plan(total=1000, due_date=_venc(30), today=_HOY.isoformat(), paid=1200)
chk("dunning sobre-pagada → cobrado", p3["stage"], "cobrado")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--iters", type=int, default=5000)
    a = ap.parse_args()
    rnd = random.Random(13)
    for _ in range(a.iters):
        total = round(rnd.uniform(0, 100000), 2)
        paid = round(rnd.uniform(0, total + 5000), 2)
        overdue = rnd.randint(-30, 400)
        rate = rnd.choice([None, 0.0, 3.5, 8.0, 12.0])
        pl = dunning_plan(
            total=total,
            due_date=_venc(overdue),
            today=_HOY.isoformat(),
            paid=paid,
            annual_rate_pct=rate,
        )
        out = pl["outstanding"]
        # INV1: saldo = total − paid (o 0 si ya cobrada)
        esp = round(total - paid, 2)
        if esp > 0 and out != esp:
            fallos.append(f"INV saldo: total={total} paid={paid} out={out} esp={esp}")
        if esp <= 0 and pl["stage"] != "cobrado":
            fallos.append(f"INV cobrada: total={total} paid={paid} stage={pl['stage']}")
        # INV2: interés ≥ 0; y 0 si no vencido o sin saldo
        inter = pl.get("interest", {})
        amt = inter.get("amount")
        if amt is not None:
            if amt < 0:
                fallos.append(f"INV interés<0: {amt}")
            if (overdue <= 0 or out <= 0) and amt != 0:
                fallos.append(f"INV interés debe 0: overdue={overdue} out={out} amt={amt}")
            # INV3: fórmula exacta cuando hay tipo y está vencida con saldo
            if rate is not None and overdue > 0 and out > 0 and not inter.get("rate_required"):
                f = round(out * (rate / 100.0) * (overdue / 365.0), 2)
                if amt != f:
                    fallos.append(
                        f"INV fórmula: out={out} rate={rate} ov={overdue} amt={amt} esp={f}"
                    )
        # INV4: etapa coherente con días vencidos
        if out > 0 and pl["stage"] != escalation_stage(overdue):
            fallos.append(f"INV etapa: overdue={overdue} stage={pl['stage']}")

    for f in fallos[:25]:
        print("  XX " + f)
    print(
        f"\n== auditoría cobro: {len(fallos)} fallos (manuales + {a.iters} fuzz) — deben ser 0 =="
    )
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
