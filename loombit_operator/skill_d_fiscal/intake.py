"""
intake.py — Skill D Fiscal: de factura extraída (docs_intel) a línea de IVA del 303.

Convierte los campos de una factura (base, IVA) en una `LineaIVA`, infiriendo el tipo de
forma **determinista** y **absteniéndose** si no es estándar (no se adivina). Registra cada
factura como un Expediente `factura_intake` (trazabilidad + PDF con huella). La extracción del
texto sigue en `docs_intel` (regex local); la mejora con 14B/visión para facturas difíciles o
escaneadas queda **pendiente**. Ver `docs/PLATAFORMA_FISCAL_ANALISIS.md`.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from ..docs_intel import InvoiceFields
from ..expedientes import Expediente, ExpedienteStore
from .modelo_303 import LineaIVA, Resultado303, procesar_303

_TIPOS = [Decimal("0.21"), Decimal("0.10"), Decimal("0.04"), Decimal("0.00")]
_CENT = Decimal("0.01")


def inferir_tipo_iva(base: float | Decimal, iva: float | Decimal) -> Decimal | None:
    """Devuelve el tipo estándar cuya cuota (base × tipo) cuadra con el IVA declarado al
    céntimo; None si ninguno encaja (no se adivina). Robusto al tamaño de la base."""
    base_d = Decimal(str(base))
    iva_d = Decimal(str(iva))
    if base_d <= 0:
        return None
    for tipo in _TIPOS:
        cuota = (base_d * tipo).quantize(_CENT, rounding=ROUND_HALF_UP)
        if abs(cuota - iva_d) <= _CENT:
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


def recopilar_lineas(store: ExpedienteStore) -> tuple[list[LineaIVA], list[str]]:
    """Reúne las líneas de IVA de todos los expedientes `factura_intake` registrados."""
    lineas: list[LineaIVA] = []
    avisos: list[str] = []
    for exp in store.list(kind="factura_intake"):
        fields = exp.data.get("fields", {})
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
    return lineas, avisos


def liquidar_303_periodo(
    store: ExpedienteStore, periodo: str, actor: str = "loombit"
) -> tuple[Expediente, Resultado303]:
    """Reúne las facturas registradas → calcula el 303 → expediente `PENDING_APPROVAL`.

    Las facturas ilegibles NO se inventan: se agregan sus avisos para que el humano las revise.
    """
    lineas, avisos_intake = recopilar_lineas(store)
    exp, res = procesar_303(store, lineas, periodo, actor=actor)
    if avisos_intake:
        res.avisos.extend(avisos_intake)
        store.update_data(exp.id, {"avisos": res.avisos}, actor)
    return store.get(exp.id), res
