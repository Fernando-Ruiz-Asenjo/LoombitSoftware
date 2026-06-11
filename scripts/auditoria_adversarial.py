"""Auditoría adversarial del camino crítico (cobros / intake / 303 / conciliación).
Cada caso intenta HACER FALLAR a Loombit. Veredicto por caso:
  CAZADO   = encontré un fallo real reproducible
  AGUANTA  = el sistema resistió el ataque
  A-VERIFICAR = depende de un criterio externo (se marca, no se afirma)
"""

import sys
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
from loombit_operator.cobros import dunning_plan, late_interest  # noqa: E402
from loombit_operator.conciliacion import Movimiento, Pendiente, conciliar  # noqa: E402
from loombit_operator.cuentas_cobrar import CuentaCobrar  # noqa: E402
from loombit_operator.docs_intel import InvoiceFields, extract_invoice_fields  # noqa: E402
from loombit_operator.expedientes import ExpedienteStore  # noqa: E402
from loombit_operator.skill_d_fiscal.intake import (  # noqa: E402
    inferir_tipo_iva,
    liquidar_303_periodo,
    rango_trimestre,
    registrar_factura,
)
from loombit_operator.tipos_demora import interes_demora_legal  # noqa: E402

hallazgos = []


def caso(n, titulo, veredicto, detalle):
    print(f"\n[{n}] {titulo}\n    VEREDICTO: {veredicto}\n    {detalle}")
    hallazgos.append((n, veredicto, titulo))


# ── T1 · Factura con fecha ESPAÑOLA (15/04/2026) → ¿entra en el 303 del 2T? ──
with tempfile.TemporaryDirectory() as tmp:
    store = ExpedienteStore(entity_id="auditoria", base_dir=Path(tmp))
    inv = InvoiceFields(
        numero="F-2026-001",
        base_imponible=1000.0,
        iva=210.0,
        proveedor="Acme SL",
        fecha="15/04/2026",
    )
    registrar_factura(store, inv, "devengado")
    exp, res = liquidar_303_periodo(store, "2T 2026")
    incluida = res.iva_devengado == Decimal("210.00")
    caso(
        "T1",
        "fecha española '15/04/2026' en el 303 del 2T 2026",
        "AGUANTA" if incluida else "CAZADO",
        f"iva_devengado={res.iva_devengado} (esperado legal: 210.00) · avisos={res.avisos}",
    )

# ── T1b · ¿qué formato de fecha emite realmente docs_intel? ──
texto = "FACTURA F-77\nFecha de factura: 03/02/2026\nBase imponible: 1.000,00\nIVA 21%: 210,00\n"
f = extract_invoice_fields(texto)
caso(
    "T1b",
    "formato de fecha que emite el extractor real",
    "INFO",
    f"docs_intel extrajo fecha={f.fecha!r} (¿ISO o dd/mm?)",
)

# ── T2 · La MISMA factura registrada DOS veces → ¿303 duplicado? ──
with tempfile.TemporaryDirectory() as tmp:
    store = ExpedienteStore(entity_id="auditoria", base_dir=Path(tmp))
    inv = InvoiceFields(numero="F-DUP-1", base_imponible=1000.0, iva=210.0, fecha="2026-04-15")
    registrar_factura(store, inv, "devengado")
    registrar_factura(store, inv, "devengado")  # mismo numero, mismo importe
    exp, res = liquidar_303_periodo(store, "2T 2026")
    caso(
        "T2",
        "misma factura (mismo nº) registrada 2 veces → 303",
        "CAZADO" if res.iva_devengado == Decimal("420.00") else "AGUANTA",
        f"iva_devengado={res.iva_devengado} (si 420.00 → DOBLE CÓMPUTO sin aviso de duplicado; "
        f"avisos={res.avisos})",
    )

# ── T3 · inferir_tipo_iva con IVA=0 y base pequeña → ¿inventa 21%? ──
r1 = inferir_tipo_iva(Decimal("0.04"), Decimal("0.00"))
r2 = inferir_tipo_iva(Decimal("0.10"), Decimal("0.01"))
caso(
    "T3",
    "inferencia de tipo con importes diminutos (ambigüedad al céntimo)",
    "CAZADO" if (r1 == Decimal("0.21") or r2 == Decimal("0.21")) else "AGUANTA",
    f"base=0.04, IVA=0.00 → tipo={r1} (legal: 0.00 o abstención) · "
    f"base=0.10, IVA=0.01 → tipo={r2} (10% también cuadra: ambiguo)",
)

# ── T4 · paid NEGATIVO (extracción del 14B garbeada) → ¿reclama MÁS del total? ──
try:
    p = dunning_plan(total=1000.0, due_date="2026-05-01", today="2026-06-11", paid=-200.0)
    caso(
        "T4",
        "paid=-200 (entrada hostil vía tool del 14B)",
        "CAZADO" if p["outstanding"] > 1000.0 else "AGUANTA",
        f"outstanding={p['outstanding']} sobre un total de 1000.00 · action={p.get('action')}",
    )
except ValueError as e:
    caso(
        "T4",
        "paid=-200 (entrada hostil vía tool del 14B)",
        "AGUANTA",
        f"rechazado con ValueError: {e}",
    )

# ── T5 · paid > total → ¿no_reclamar? ──
p = dunning_plan(total=1000.0, due_date="2026-05-01", today="2026-06-11", paid=1500.0)
caso(
    "T5",
    "pago superior al total (1500 sobre 1000)",
    "AGUANTA" if p["action"] == "no_reclamar" else "CAZADO",
    f"action={p['action']} outstanding={p.get('outstanding')}",
)

# ── T6 · total NEGATIVO (rectificativa) → ¿la llama 'factura_cobrada'? ──
p = dunning_plan(total=-242.0, due_date="2026-05-01", today="2026-06-11")
caso(
    "T6",
    "total=-242 (rectificativa) en el plan de cobro",
    "CAZADO" if p.get("reason") == "factura_cobrada" else "AGUANTA",
    f"reason={p.get('reason')} action={p.get('action')} (esperado: revisar, no 'cobrada')",
)

# ── T7 · interés con tramo FUERA de la tabla BOE → ¿se abstiene? ──
r = interes_demora_legal(1000.0, "2026-06-20", "2026-07-15")  # cruza al 2S2026 (no publicado)
caso(
    "T7",
    "interés con tramo en 2S2026 (sin publicar) → abstención",
    "AGUANTA" if r.get("rate_required") else "CAZADO",
    f"rate_required={r.get('rate_required')} amount={r.get('amount')} note={r.get('note', '')[:70]}",
)

# ── T7b · frontera exacta de semestre (vence 30/06, hoy 01/07) ──
r = interes_demora_legal(1000.0, "2025-12-31", "2026-01-01")
caso(
    "T7b",
    "frontera 31/12→01/01: 1 día al tipo del 1S2026",
    (
        "AGUANTA"
        if r.get("tramos")
        and r["tramos"][0]["dias"] == 1
        and r["tramos"][0]["semestre"] == "1S2026"
        else "CAZADO"
    ),
    f"tramos={r.get('tramos')}",
)

# ── T8 · año bisiesto: base 365 fija (2024 tiene 366 días) ──
r = interes_demora_legal(10000.0, "2023-12-31", "2024-12-31")  # todo 2024
dias = sum(t["dias"] for t in r.get("tramos", []))
caso(
    "T8",
    "devengo de TODO 2024 (bisiesto) con base_dias=365",
    "A-VERIFICAR",
    f"días computados={dias} (366 reales), base divisor=365 → interés anual efectivo "
    f"{dias}/365 = {dias/365:.4f} del tipo. Criterio (365 vs 366) a confirmar con asesor/jurisprudencia.",
)

# ── T9 · redondeo float (banker's) en dinero ──
o = dunning_plan(total=100.005, due_date="2026-05-01", today="2026-06-11")["outstanding"]
i = late_interest(5004.10, 73, 10.15)["amount"]
i_dec = (Decimal("5004.10") * Decimal("10.15") / 100 * 73 / 365).quantize(Decimal("0.01"))
caso(
    "T9",
    "redondeo de dinero con float/round() vs Decimal HALF_UP",
    "CAZADO" if str(i) != str(i_dec) else "A-VERIFICAR",
    f"outstanding(100.005)={o} · interés float={i} vs Decimal HALF_UP={i_dec} "
    f"(el propio repo exige Decimal sin float para dinero en conciliación, D-14)",
)


# ── T10 · dos abonos idénticos contra UNA pendiente → ¿doble conciliación? ──
def _mov(d, imp, ref):
    return Movimiento(
        fecha_operacion=d,
        fecha_valor=d,
        importe=Decimal(imp),
        concepto_comun="",
        concepto_propio="",
        num_documento="",
        referencia1=ref,
        referencia2="",
        conceptos=[],
    )


mov1 = _mov(date(2026, 6, 1), "500.00", "TRANSFERENCIA CLIENTE X")
mov2 = _mov(date(2026, 6, 2), "500.00", "TRANSFERENCIA CLIENTE X")
pend = [Pendiente(id="p1", importe=Decimal("500.00"), referencia="F-9", contraparte="Cliente X")]
rr = conciliar([mov1, mov2], pend)
dobles = sum(1 for c in rr if c.pendiente is not None and c.pendiente.id == "p1")
caso(
    "T10",
    "dos abonos de 500€ contra UNA única pendiente de 500€",
    "CAZADO" if dobles == 2 else "AGUANTA",
    f"conciliaciones hacia p1: {dobles}/2 abonos · tiers={[str(c.tier) for c in rr]} "
    f"(si 2 → la misma factura se 'cobra' dos veces; el 2º abono debería abstener/avisar)",
)

# ── T11 · cuenta que vence HOY: ¿vencida o pendiente? ──
c = CuentaCobrar(cliente="X", importe=100.0, vencimiento="2026-06-11")
p = dunning_plan(total=100.0, due_date="2026-06-11", today="2026-06-11")
caso(
    "T11",
    "factura que vence hoy (frontera)",
    "AGUANTA" if p["stage"] == "vence_hoy" and p["action"] == "preparar_recordatorio" else "CAZADO",
    f"stage={p['stage']} action={p['action']} (esperado: vence_hoy, sin interés ni 40€)",
)

# ── T12 · '4T' pedido en enero → ¿de qué año? ──
d, h, et = rango_trimestre("4T")
caso(
    "T12",
    "'4T' sin año (pedido p.ej. en enero)",
    "A-VERIFICAR",
    f"resuelve a {et} (año en curso {date.today().year}). En enero, '4T' casi siempre "
    f"significa el año ANTERIOR → riesgo de 303 del trimestre equivocado.",
)

# ── T13 · el 14B puede INYECTAR un tipo de interés inventado vía tool ──
p = dunning_plan(
    total=1000.0, due_date="2026-04-01", today="2026-06-11", annual_rate_pct=25.0
)  # tipo inventado, sin BOE
etiquetado = p.get("interest", {}).get("tipo_manual") and "BOE" in p["interest"].get("fuente", "")
caso(
    "T13",
    "tipo_interes_anual=25% inyectado (sin fuente BOE) por el extractor",
    "AGUANTA" if etiquetado else "CAZADO",
    f"interest={p['interest']}",
)

print("\n" + "=" * 70)
caz = [h for h in hallazgos if h[1] == "CAZADO"]
ag = [h for h in hallazgos if h[1] == "AGUANTA"]
av = [h for h in hallazgos if h[1] in ("A-VERIFICAR", "INFO")]
print(f"RESUMEN: {len(caz)} CAZADOS · {len(ag)} AGUANTAN · {len(av)} A-VERIFICAR/INFO")
for n, v, t in hallazgos:
    print(f"  {v:12s} {n:4s} {t}")
sys.exit(1 if caz else 0)
