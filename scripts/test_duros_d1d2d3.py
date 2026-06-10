"""
TESTS DUROS para los 3 fixes de diseño (encargo de Fernando: «test duros a D-1, D-2 y D-3»).
Adversarial: fraseos COLOQUIALES/ofuscados (sin keywords obvias), números TRAMPA (importes que
parecen años), multi-turno, + invariantes NEGATIVOS («no sobre-disparar»). En VIVO con el 14B real.

- D-1 (routing): fraseos raros que el regex falla → el clasificador LLM debe rutear; y los que NO
  debe rutear (conciliación, redacción libre).
- D-2 (guardas de dominio): intentos retorcidos de que haga lo no modelado (retención/IBAN/modelos)
  → abstención honesta; y los que NO debe abstener (sin retención, 303 sí modelado).
- D-3 (extracción): importes que el 14B garbea (negativos, total-vs-base, IVA incluido, año-like,
  separadores) → cifra correcta; + no sobre-corregir multi-importe.

Uso:  python scripts/test_duros_d1d2d3.py [--solo <id>]
Formato: (id, facturas|None, history|None, task, check(r, tools, x) -> bool)
"""

from __future__ import annotations

import argparse
import contextlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from funcional_live import _emit  # noqa: E402
from funcional_live3 import (  # noqa: E402
    _H,
    _con_timeout,
    _entidad_aislada,
    _run,
    _run_hist,
    _stub_send,
)


def _num(x, *trozos):
    """Todos los trozos (sin separadores de miles) aparecen en x."""
    plano = x.replace(".", "").replace(",", "")
    return all(t in plano for t in trozos)


ESCENARIOS = [
    # ══ D-1 · ROUTING (el regex falla → el clasificador LLM rutea) ════════════════════════════════
    (
        "d1_morosos",
        [_emit(1000, c="Acme"), _emit(2000, c="López")],
        None,
        "Ponme al día de lo que me adeudan los morosos.",
        lambda r, t, x: "cobros_pendientes" in t,
    ),
    (
        "d1_tesoreria",
        [_emit(1500)],
        None,
        "¿Qué pinta tiene mi tesorería ahora mismo?",
        lambda r, t, x: any(
            k in t for k in ("resumen_financiero", "resumen_facturacion", "cobros_pendientes")
        ),
    ),
    (
        "d1_hacienda_correo",
        None,
        None,
        "Échale un ojo a mi correo a ver si hay algo de Hacienda.",
        lambda r, t, x: "gmail_search" in t,
    ),
    (
        "d1_liquidacion_iva",
        [_emit(1000, fecha="2026-05-10")],
        None,
        "Tírame la liquidación trimestral del IVA con lo que tengo apuntado.",
        # 303-intent: o calcula, o pregunta honestamente el periodo (ambas engagement con el 303).
        lambda r, t, x: "calcular_303_registradas" in t
        or "calcular_303" in t
        or any(k in x for k in ("periodo", "período", "trimestre")),
    ),
    (
        "d1_mete_factura",
        [],
        None,
        "Mete en el sistema lo que le facturé a Endesa: 800 € más su IVA al 21%, el 5 de junio de 2026.",
        lambda r, t, x: "registrar_factura" in t and _num(x, "800"),
    ),
    (
        "d1_pasta_deben",
        [_emit(1500, c="X")],
        None,
        "¿Cuánta pasta me deben por ahí?",
        lambda r, t, x: "cobros_pendientes" in t,
    ),
    (
        "d1_conciliacion_NEG",
        None,
        None,
        "Concíliame el banco con mis cobros de este mes.",
        lambda r, t, x: "cobros_pendientes" not in t
        and any(k in x for k in ("n43", "norma 43", "extracto", "necesito")),
    ),
    (
        "d1_redacta_correo_NEG",
        None,
        None,
        "Redáctame un correo a Ana sobre la reunión del lunes.",
        lambda r, t, x: not any(
            k in t for k in ("registrar_factura", "cobros_pendientes", "calcular_303", "plan_cobro")
        ),
    ),
    # ══ D-2 · GUARDAS DE DOMINIO (abstención honesta de lo no modelado) ════════════════════════════
    (
        "d2_minuta_irpf",
        None,
        None,
        "Hazme la minuta del abogado: 1000 € menos el 15% de IRPF que me retienen.",
        lambda r, t, x: "retenci" in x and "✅" not in x,
    ),
    (
        "d2_iban_malo",
        None,
        None,
        "Apúntame el IBAN de pago de Acme: ES00 0000 0000 0000 0000 0000.",
        lambda r, t, x: "iban" in x and not ("✅" in x and "guardad" in x),
    ),
    (
        "d2_modelo_130",
        None,
        None,
        "Prepárame el 130 del pago fraccionado de este trimestre.",
        lambda r, t, x: "130" in x and "✅" not in x,
    ),
    (
        "d2_modelo_349",
        None,
        None,
        "Hazme el modelo 349 de operaciones intracomunitarias.",
        lambda r, t, x: "349" in x and "✅" not in x,
    ),
    (
        "d2_retencion_multiturno",
        None,
        _H(
            "Quiero facturar a un cliente.",
            "Dime importe, tipo de IVA y fecha.",
        ),
        "Emite la factura de 1000 € al 21% con la retención del 15% de IRPF, fecha 5 de junio de 2026.",
        lambda r, t, x: "retenci" in x and "✅" not in x,
    ),
    (
        "d2_sin_retencion_NEG",
        [],
        None,
        "Registra una factura a López de 1000 € al 21% SIN retención, fecha 5 de junio de 2026.",
        lambda r, t, x: "registrar_factura" in t and "✅" in x,
    ),
    (
        "d2_303_modelado_NEG",
        [_emit(1000, fecha="2026-05-10")],
        None,
        "Calcula mi modelo 303 del 2T 2026 con lo registrado.",
        lambda r, t, x: ("calcular_303_registradas" in t or "calcular_303" in t)
        and "todavía no calculo el modelo" not in x,
    ),
    (
        "d2_303_no_abstiene",
        None,
        None,
        "Prepárame el 303 con ventas de 1000 € al 21% y sin compras.",
        lambda r, t, x: "todavía no calculo el modelo" not in x,
    ),
    # ══ D-3 · EXTRACCIÓN DE IMPORTES (la cifra la pone el CÓDIGO) ══════════════════════════════════
    (
        "d3_negativa",
        [],
        None,
        "Registra una factura rectificativa a López, base imponible -200 € e IVA al 21%, fecha 5 de junio de 2026.",
        lambda r, t, x: "registrar_factura" in t and _num(x, "200") and "242" in x.replace(".", ""),
    ),
    (
        "d3_total_vs_base",
        [],
        None,
        "Apúntame una factura emitida a López de 2000 € al 21%, fecha 5 de junio de 2026.",
        lambda r, t, x: "registrar_factura" in t and _num(x, "2000") and _num(x, "2420"),
    ),
    (
        "d3_iva_incluido",
        [],
        None,
        "Apúntame una factura emitida a López de 1210 € IVA incluido al 21%, fecha 5 de junio de 2026.",
        lambda r, t, x: "registrar_factura" in t and _num(x, "1000") and _num(x, "1210"),
    ),
    (
        "d3_year_like_amount",
        [],
        None,
        "Apúntame una factura emitida a López de 2026 € al 21%, fecha 5 de junio de 2026.",
        lambda r, t, x: "registrar_factura" in t and _num(x, "2026"),
    ),
    (
        "d3_iva_incluido_10",
        [],
        None,
        "Apúntame una factura emitida a López de 1100 € IVA incluido al 10%, fecha 5 de junio de 2026.",
        lambda r, t, x: "registrar_factura" in t and _num(x, "1000") and _num(x, "1100"),
    ),
    (
        "d3_big_sep_cobro",
        None,
        None,
        "Reclama una factura de 1.000.000,50 € vencida el 1 de mayo de 2026. Solo números.",
        lambda r, t, x: "plan_cobro" in t and _num(x, "1000000"),
    ),
    (
        "d3_cobro_decimal",
        None,
        None,
        "Reclama 1234,56 € de una factura vencida el 1 de mayo de 2026. Solo números.",
        lambda r, t, x: "plan_cobro" in t and _num(x, "123456"),
    ),
    (
        "d3_multi_amount_NEG",
        [],
        None,
        "Apunta la factura emitida a López de 350 € al 21%, fecha 5 de junio de 2026.",
        lambda r, t, x: "registrar_factura" in t and _num(x, "350"),
    ),
]


def correr(filtro):
    fallos, n = 0, 0
    grupos: dict[str, list[int]] = {}
    for cid, facturas, history, task, check in ESCENARIOS:
        if filtro and filtro not in cid:
            continue
        n += 1
        fam = cid.split("_")[0]
        grupos.setdefault(fam, [0, 0])
        grupos[fam][1] += 1
        try:
            ctx = _entidad_aislada(facturas) if facturas is not None else contextlib.nullcontext()
            with ctx, _stub_send():
                _fn = (lambda: _run_hist(task, history)) if history else (lambda: _run(task))
                r, t, x = _con_timeout(_fn)
            ok = bool(check(r, t, x))
            detalle = (x or "").replace("\n", " ")[:72]
        except Exception as exc:  # noqa: BLE001
            ok, detalle = False, ("EXC: " + repr(exc))[:72]
        if ok:
            grupos[fam][0] += 1
        else:
            fallos += 1
        print(f"  {'PASS' if ok else 'FAIL':4} {cid:26} | {detalle}")
    print()
    for fam in sorted(grupos):
        ok, tot = grupos[fam]
        print(f"  {fam.upper()}: {ok}/{tot}")
    print(f"\n== {n - fallos}/{n} verde · fallos: {fallos} ==")
    return fallos


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--solo", type=str, default=None)
    args = ap.parse_args()
    return 1 if correr(args.solo) else 0


if __name__ == "__main__":
    raise SystemExit(main())
