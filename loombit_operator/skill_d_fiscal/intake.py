"""
intake.py — Skill D Fiscal: de factura extraída (docs_intel) a línea de IVA del 303.

Convierte los campos de una factura (base, IVA) en una `LineaIVA`, infiriendo el tipo de
forma **determinista** y **absteniéndose** si no es estándar (no se adivina). Registra cada
factura como un Expediente `factura_intake` (trazabilidad + PDF con huella). La extracción del
texto sigue en `docs_intel` (regex local); la mejora con 14B/visión para facturas difíciles o
escaneadas queda **pendiente**. Ver `docs/PLATAFORMA_FISCAL_ANALISIS.md`.
"""

from __future__ import annotations

import re
from calendar import monthrange
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from ..docs_intel import InvoiceFields
from ..expedientes import Expediente, ExpedienteStore
from .modelo_303 import LineaIVA, Resultado303, procesar_303

_TRIM_MESES = {1: (1, 3), 2: (4, 6), 3: (7, 9), 4: (10, 12)}
_TRIM_PALABRA = {"primer": 1, "segundo": 2, "tercer": 3, "cuarto": 4}


def rango_trimestre(periodo: str | None) -> tuple[date | None, date | None, str]:
    """Convierte '2T 2026' / 'segundo trimestre 2026' / '2T' en (desde, hasta, etiqueta).

    Devuelve (None, None, …) si no hay trimestre claro → el llamante NO filtra (y avisa). El 303 de
    un trimestre SOLO puede incluir facturas de ese trimestre; sin esto se sumaba TODO el año.
    """
    s = (periodo or "").lower()
    q: int | None = None
    m = re.search(r"\b([1-4])\s*t\b", s)
    if m:
        q = int(m.group(1))
    else:
        for palabra, n in _TRIM_PALABRA.items():
            if palabra in s:
                q = n
                break
    if q is None:
        return None, None, (periodo or "todas las facturas")
    my = re.search(r"\b(20\d{2})\b", s)
    anio = int(my.group(1)) if my else date.today().year
    m0, m1 = _TRIM_MESES[q]
    return date(anio, m0, 1), date(anio, m1, monthrange(anio, m1)[1]), f"{q}T {anio}"


_MES_NOMBRE = [
    "",
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
]
_MES_NUM = {n: i for i, n in enumerate(_MES_NOMBRE) if n}
_MES_NUM["setiembre"] = 9


def rango_periodo(
    periodo: str | None, hoy: date | None = None
) -> tuple[date | None, date | None, str]:
    """Rango (desde, hasta, etiqueta) de un periodo: trimestre ('2T'), MES ('junio'/'este mes') o None
    (todo). Generaliza `rango_trimestre` para soportar también meses — base de «cuánto he facturado».
    """
    hoy = hoy or date.today()
    d, h, et = rango_trimestre(periodo)
    if d is not None:
        return d, h, et
    s = (periodo or "").lower()
    if "este mes" in s or "mes actual" in s or "del mes" in s or "este_mes" in s:
        m, anio = hoy.month, hoy.year
    else:
        m = next((n for nombre, n in _MES_NUM.items() if nombre in s), None)
        if m is None:
            return None, None, (periodo or "todo")
        my = re.search(r"\b(20\d{2})\b", s)
        anio = int(my.group(1)) if my else hoy.year
    return date(anio, m, 1), date(anio, m, monthrange(anio, m)[1]), f"{_MES_NOMBRE[m]} {anio}"


_TIPOS = [Decimal("0.21"), Decimal("0.10"), Decimal("0.04"), Decimal("0.00")]
_CENT = Decimal("0.01")


def inferir_tipo_iva(base: float | Decimal, iva: float | Decimal) -> Decimal | None:
    """Devuelve el tipo estándar cuya cuota (|base| × tipo) cuadra con el |IVA| declarado al céntimo;
    None si ninguno encaja (no se adivina). Robusto al tamaño de la base. Acepta importes NEGATIVOS
    (rectificativas/abonos): el tipo se infiere por valor absoluto y el signo se conserva en la
    LineaIVA, de modo que una devolución REDUCE el devengado del 303 (antes se caía → 303 inflado).
    """
    base_d = Decimal(str(base))
    iva_d = Decimal(str(iva))
    if base_d == 0:
        return None  # sin base no se puede inferir
    for tipo in _TIPOS:
        cuota = (abs(base_d) * tipo).quantize(_CENT, rounding=ROUND_HALF_UP)
        if abs(cuota - abs(iva_d)) <= _CENT:
            return tipo
    return None


def linea_desde_factura(inv: InvoiceFields, sentido: str) -> tuple[LineaIVA | None, list[str]]:
    """Construye la `LineaIVA` del 303 desde una factura extraída. Abstención honesta."""
    ref = inv.numero or "s/n"
    if inv.base_imponible is None or inv.iva is None:
        return None, [f"Factura {ref}: sin base/IVA legibles → revisar manualmente."]
    tipo = inferir_tipo_iva(inv.base_imponible, inv.iva)
    if tipo is None:
        return None, [
            f"Factura {ref}: tipo de IVA no estándar (base {inv.base_imponible}, IVA {inv.iva}) "
            "→ revisar (¿recargo de equivalencia, varios tipos, inversión de sujeto pasivo?)."
        ]
    linea = LineaIVA(
        base=inv.base_imponible,
        tipo=tipo,
        sentido=sentido,
        cuota=inv.iva,
        concepto=f"Factura {ref}",
    )
    return linea, []


def registrar_factura(
    store: ExpedienteStore,
    inv: InvoiceFields,
    sentido: str,
    pdf_path: Path | None = None,
) -> Expediente:
    """Registra una factura como Expediente `factura_intake` (campos + PDF con huella + traza)."""
    ref = inv.numero or "s/n"
    exp = store.create(
        "factura_intake",
        f"Factura {ref}",
        data={"sentido": sentido, "fields": inv.to_dict()},
    )
    if pdf_path is not None:
        store.attach_document(exp.id, "factura_pdf", Path(pdf_path))
    if inv.missing:
        store.add_event(exp.id, "campos_faltantes", {"missing": inv.missing}, "loombit")
    return exp


def recopilar_lineas(
    store: ExpedienteStore, desde: date | None = None, hasta: date | None = None
) -> tuple[list[LineaIVA], list[str]]:
    """Reúne las líneas de IVA de los expedientes `factura_intake`. Si se da [desde, hasta], SOLO las
    facturas cuya fecha cae en ese rango (el 303 de un trimestre no puede mezclar trimestres)."""
    lineas: list[LineaIVA] = []
    avisos: list[str] = []
    filtrar = desde is not None and hasta is not None
    fuera, sin_fecha = 0, 0
    for exp in store.list(kind="factura_intake"):
        fields = exp.data.get("fields", {})
        if filtrar:
            try:
                f = date.fromisoformat(str(fields.get("fecha") or "")[:10])
            except ValueError:
                sin_fecha += 1
                continue  # sin fecha legible no se puede ubicar en un trimestre → no se incluye
            if not (desde <= f <= hasta):
                fuera += 1
                continue
        inv = InvoiceFields(
            numero=fields.get("numero"),
            base_imponible=fields.get("base_imponible"),
            iva=fields.get("iva"),
            proveedor=fields.get("proveedor"),
        )
        linea, avs = linea_desde_factura(inv, exp.data.get("sentido", "soportado"))
        avisos.extend(avs)
        if linea is not None:
            lineas.append(linea)
    if fuera:
        avisos.append(f"{fuera} factura(s) de otros periodos quedaron fuera de este trimestre.")
    if sin_fecha:
        avisos.append(
            f"{sin_fecha} factura(s) sin fecha legible NO se incluyeron en el periodo; revísalas."
        )
    return lineas, avisos


def liquidar_303_periodo(
    store: ExpedienteStore, periodo: str, actor: str = "loombit"
) -> tuple[Expediente, Resultado303]:
    """Reúne las facturas registradas → calcula el 303 → expediente `PENDING_APPROVAL`.

    Las facturas ilegibles NO se inventan: se agregan sus avisos para que el humano las revise.
    """
    desde, hasta, _ = rango_trimestre(periodo)
    lineas, avisos_intake = recopilar_lineas(store, desde, hasta)
    exp, res = procesar_303(store, lineas, periodo, actor=actor)
    if avisos_intake:
        res.avisos.extend(avisos_intake)
        store.update_data(exp.id, {"avisos": res.avisos}, actor)
    return store.get(exp.id), res
