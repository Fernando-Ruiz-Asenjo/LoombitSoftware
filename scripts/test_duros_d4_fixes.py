"""
TESTS DUROS EN VIVO de la superficie del 14B: D-4 (comparativas/predicciones), los FIXES nuevos de la
auditoría que pasan por el 14B→guarda (modelos 100/200/720, IRPF-en-factura, «millones»), y REGRESIÓN
de D-1/D-2/D-3 por fraseos FRESCOS. El 14B real (mismo motor que el server). Provocar el fallo.

Uso:  python scripts/test_duros_d4_fixes.py [--solo <id>]
Formato: (id, facturas|None, history|None, task, check(r, tools, x) -> bool)
"""

from __future__ import annotations

import argparse
import contextlib
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from funcional_live import _emit  # noqa: E402
from funcional_live3 import (  # noqa: E402
    _con_timeout,
    _entidad_aislada,
    _run,
    _stub_send,
)
from loombit_operator.tools import dominio as _Dm  # noqa: E402

# fechas reales: mes ACTUAL y ANTERIOR (para que el comparativo tenga datos en ambos)
_, (_DA, _, _ETA), (_DB, _, _ETB) = _Dm._periodos_comparados("mes", date.today())
_, (_QA, _, _QETA), (_QB, _, _QETB) = _Dm._periodos_comparados("trimestre", date.today())


def _num(x, *trozos):
    plano = x.replace(".", "").replace(",", "")
    return all(t in plano for t in trozos)


def _emf(base, fecha):  # emitida en una fecha concreta
    return _emit(base, fecha=fecha)


ESCENARIOS = [
    # ══ D-4 · COMPARATIVAS (el 14B debe rutear a resumen_comparativo con las cifras del código) ══
    (
        "d4_mas_que_mes_pasado",
        [_emf(2000, _DA.isoformat()), _emf(1000, _DB.isoformat())],
        None,
        "¿He facturado más este mes que el mes pasado?",
        lambda r, t, x: "resumen_comparativo" in t and _num(x, "2000") and _num(x, "1000"),
    ),
    (
        "d4_crecimiento",
        [_emf(3000, _DA.isoformat()), _emf(2000, _DB.isoformat())],
        None,
        "¿Cuánto he crecido este mes respecto al anterior?",
        lambda r, t, x: "resumen_comparativo" in t and _num(x, "3000") and _num(x, "2000"),
    ),
    (
        "d4_evolucion",
        [_emf(1500, _DA.isoformat())],
        None,
        "Enséñame la evolución de mi facturación.",
        lambda r, t, x: "resumen_comparativo" in t,
    ),
    (
        "d4_trimestre",
        [_emf(5000, _QA.isoformat()), _emf(4000, _QB.isoformat())],
        None,
        "¿Voy mejor este trimestre que el anterior?",
        lambda r, t, x: "resumen_comparativo" in t,
    ),
    (
        "d4_coloquial_vendo",
        [_emf(2000, _DA.isoformat()), _emf(1000, _DB.isoformat())],
        None,
        "¿Vendo más o menos que el mes pasado?",
        lambda r, t, x: "resumen_comparativo" in t,
    ),
    # PREDICCIÓN del futuro → abstención (NO comparativo, NO un número inventado)
    (
        "d4_prediccion_NEG",
        [_emf(1000, _DA.isoformat())],
        None,
        "¿Cuánto voy a facturar el mes que viene?",
        lambda r, t, x: "resumen_comparativo" not in t
        and any(k in x for k in ("no ", "no puedo", "no tengo", "futur", "predec", "estim")),
    ),
    (
        "d4_a_este_ritmo_NEG",
        [],
        None,
        "A este ritmo, ¿cuánto facturaré este año?",
        lambda r, t, x: "resumen_comparativo" not in t and "✅" not in x,
    ),
    # ══ D-2 · FIXES NUEVOS DE LA AUDITORÍA (14B → guarda) ══
    (
        "fix_modelo_100",
        None,
        None,
        "Hazme el modelo 100 de la renta.",
        lambda r, t, x: "100" in x and "✅" not in x,
    ),
    (
        "fix_modelo_200",
        None,
        None,
        "Prepárame el modelo 200 del impuesto de sociedades.",
        lambda r, t, x: "200" in x and "✅" not in x,
    ),
    (
        "fix_modelo_720",
        None,
        None,
        "Hazme el modelo 720 de bienes en el extranjero.",
        lambda r, t, x: "720" in x and "✅" not in x,
    ),
    (
        "fix_irpf_factura",
        [],
        None,
        "Emite una factura a López de 1000 € al 21% con IRPF del 15%, fecha 5 de junio de 2026.",
        lambda r, t, x: "retenci" in x and "✅" not in x,
    ),
    # ══ REGRESIÓN D-1/D-2/D-3 por fraseos FRESCOS ══
    (
        "reg_adeudan",
        [_emf(1500, _DA.isoformat())],
        None,
        "¿Qué me adeudan mis clientes ahora mismo?",
        lambda r, t, x: "cobros_pendientes" in t,
    ),
    (
        "reg_mete_factura",
        [],
        None,
        "Mete una factura emitida a Acme de 600 € al 21%, fecha 5 de junio de 2026.",
        lambda r, t, x: "registrar_factura" in t and _num(x, "600"),
    ),
    (
        "reg_iban_cuenta",
        None,
        None,
        "Apúntame la cuenta de pago de mi cliente: ES00 0000 0000 0000 0000 0000.",
        lambda r, t, x: not ("✅" in x and "guardad" in x),
    ),
    (
        "reg_negativo",
        [],
        None,
        "Registra una factura rectificativa a López, base imponible -300 € e IVA al 21%, fecha 5 de junio de 2026.",
        lambda r, t, x: "registrar_factura" in t or "no se pudo" in x or "rectificativa" in x,
    ),
    (
        "reg_iva_incluido",
        [],
        None,
        "Apúntame una factura emitida a López de 2420 € con IVA incluido al 21%, fecha 5 de junio de 2026.",
        lambda r, t, x: "registrar_factura" in t and _num(x, "2000"),
    ),
    (
        "reg_retencion",
        None,
        None,
        "Hazme la minuta del abogado con una retención del 7% de IRPF.",
        lambda r, t, x: "retenci" in x and "✅" not in x,
    ),
    (
        "reg_conciliacion_NEG",
        None,
        None,
        "Cuádrame el banco con mis cobros de este mes.",
        lambda r, t, x: "cobros_pendientes" not in t
        and any(k in x for k in ("n43", "norma 43", "extracto", "necesito")),
    ),
    (
        "reg_303_registradas",
        [_emf(1000, _QA.isoformat())],
        None,
        "Calcula mi 303 del trimestre con lo que tengo registrado.",
        lambda r, t, x: "calcular_303_registradas" in t or "calcular_303" in t or "303" in x,
    ),
]


def correr(filtro):
    fallos, n = 0, 0
    for cid, facturas, history, task, check in ESCENARIOS:
        if filtro and filtro not in cid:
            continue
        n += 1
        try:
            ctx = _entidad_aislada(facturas) if facturas is not None else contextlib.nullcontext()
            with ctx, _stub_send():
                r, t, x = _con_timeout(lambda: _run(task))
            ok = bool(check(r, t, x))
            det = (x or "").replace("\n", " ")[:72]
        except Exception as exc:  # noqa: BLE001
            ok, det = False, ("EXC: " + repr(exc))[:72]
        if not ok:
            fallos += 1
        print(f"  {'PASS' if ok else 'FAIL':4} {cid:26} | {det}")
    print(f"\n== {n - fallos}/{n} verde · fallos: {fallos} ==")
    return fallos


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--solo", type=str, default=None)
    args = ap.parse_args()
    return 1 if correr(args.solo) else 0


if __name__ == "__main__":
    raise SystemExit(main())
