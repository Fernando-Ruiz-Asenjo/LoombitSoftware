"""
conciliacion_cobros.py — Skill D Fiscal: puente conciliación bancaria ↔ cobros.

Adapta el núcleo blanco (`conciliacion.py`, `expedientes.py`) al dominio: construye las
`Pendiente` neutras desde los expedientes `factura_intake` devengados (ventas pendientes de
cobro) y, cuando el humano confirma un match, **marca la factura como cobrada**. Ese marcado
es el cierre del bucle PERCIBIR→...: alimenta el gate S-01 de `cobros.py` ("factura ya
cobrada → no reclamar"), de modo que el cerebro de cobros deja de reclamar lo ya pagado.

El número del importe sale del extracto bancario (Decimal), no de un LLM. Sin importe fiable
en la factura, **no se concilia** (se omite): mejor "no lo sé" que un cobro inventado.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from ..conciliacion import CENT, Pendiente
from ..expedientes import Expediente, ExpedienteStore

FACTURA_KIND = "factura_intake"

# Plazo de pago LEGAL por defecto cuando la factura no pacta vencimiento (Ley 3/2004, art. 4): 30 días
# naturales desde la emisión. El interés de demora solo corre DESDE el vencimiento, no desde la emisión.
DIAS_PLAZO_LEGAL = 30


def _vencimiento_efectivo(fields: dict) -> tuple[str, bool]:
    """Vencimiento (ISO) que usar para el plan de cobro, y si fue ESTIMADO. Si la factura trae
    `vencimiento`, ese (estimado=False). Si no, aplica el plazo legal por defecto: `fecha` de emisión +
    30 días (estimado=True) — NO la fecha de emisión a pelo (eso inventaría un plazo de 0 días y
    reclamaría mora antes de tiempo). Si tampoco hay fecha de emisión, ('', False) → degradar honesto.
    """
    venc = str(fields.get("vencimiento") or "").strip()
    if venc:
        return venc, False
    emision = str(fields.get("fecha") or "").strip()
    if not emision:
        return "", False
    try:
        d = date.fromisoformat(emision[:10]) + timedelta(days=DIAS_PLAZO_LEGAL)
    except ValueError:
        return "", False
    return d.isoformat(), True


def _pagado_de(exp_data: dict) -> float:
    """Importe ya cobrado a cuenta (cobro PARCIAL) — para reclamar solo el saldo (S-03), nunca el
    total. 0.0 si no hay cobro parcial registrado."""
    if not exp_data.get("cobrado_parcial"):
        return 0.0
    try:
        return float(str(exp_data.get("importe_cobrado") or 0))
    except (TypeError, ValueError):
        return 0.0


def _importe_factura(fields: dict) -> Decimal | None:
    """Importe que se espera cobrar: total si está, si no base+IVA. None si no hay nada fiable."""
    total = fields.get("total")
    if total is None:
        base, iva = fields.get("base_imponible"), fields.get("iva")
        if base is None or iva is None:
            return None
        total = float(base) + float(iva)
    return Decimal(str(total)).quantize(CENT)


def pendientes_con_vencimiento(
    store: ExpedienteStore,
) -> list[tuple[Pendiente, str, bool, float]]:
    """Como `pendientes_de_cobro`, pero adjunta a cada partida lo necesario para calcular su plan de
    cobro (Ley 3/2004) sin que el usuario dicte nada: VENCIMIENTO efectivo (con el plazo legal por
    defecto si falta), si ese vencimiento fue ESTIMADO, y lo ya COBRADO a cuenta (cobro parcial).
    Devuelve `(Pendiente, vencimiento_iso, estimado, pagado)`; el vencimiento va vacío solo si la
    factura no trae ni vencimiento ni fecha de emisión → el llamante degrada honesto."""
    out: list[tuple[Pendiente, str, bool, float]] = []
    for exp in store.list(kind=FACTURA_KIND):
        if exp.data.get("sentido") != "devengado" or exp.data.get("cobrado"):
            continue
        fields = exp.data.get("fields", {})
        importe = _importe_factura(fields)
        if importe is None or importe <= 0:
            continue  # sin importe fiable o rectificativa (negativa) → no es una partida a reclamar
        pend = Pendiente(
            id=exp.id,
            importe=importe,
            referencia=fields.get("numero") or "",
            contraparte=fields.get("proveedor") or "",
        )
        venc, estimado = _vencimiento_efectivo(fields)
        out.append((pend, venc, estimado, _pagado_de(exp.data)))
    return out


def pendientes_de_cobro(store: ExpedienteStore) -> list[Pendiente]:
    """Partidas pendientes de cobro: facturas `devengado` (ventas) aún no marcadas cobradas."""
    return [p for p, *_ in pendientes_con_vencimiento(store)]


def rectificativas_pendientes(store: ExpedienteStore) -> list[tuple[str, Decimal]]:
    """Rectificativas (facturas `devengado` con importe NEGATIVO, aún no cobradas): `(contraparte,
    importe_negativo)`. Sirven para NETEAR la deuda de un cliente antes de reclamarle — una
    rectificativa que cancela la factura deja la deuda neta en 0 (no hay nada que reclamar)."""
    out: list[tuple[str, Decimal]] = []
    for exp in store.list(kind=FACTURA_KIND):
        if exp.data.get("sentido") != "devengado" or exp.data.get("cobrado"):
            continue
        importe = _importe_factura(exp.data.get("fields", {}))
        if importe is not None and importe < 0:
            out.append((exp.data.get("fields", {}).get("proveedor") or "", importe))
    return out


def marcar_cobrada(
    store: ExpedienteStore,
    factura_id: str,
    *,
    importe_cobrado: Decimal,
    banco_ref: str,
    fecha_cobro: str | None = None,
    parcial: bool = False,
    actor: str = "human",
) -> Expediente:
    """Marca una factura como cobrada (o cobrada en parte) tras un match confirmado por el
    humano. Deja traza inmutable (`cobro_conciliado`) y datos para el gate S-01 de cobros."""
    fecha_cobro = fecha_cobro or date.today().isoformat()
    store.update_data(
        factura_id,
        {
            "cobrado": not parcial,
            "cobrado_parcial": parcial,
            "importe_cobrado": str(importe_cobrado),
            "fecha_cobro": fecha_cobro,
            "banco_ref": banco_ref,
        },
        actor,
    )
    store.add_event(
        factura_id,
        "cobro_conciliado",
        {"importe": str(importe_cobrado), "banco_ref": banco_ref, "parcial": parcial},
        actor,
    )
    return store.get(factura_id)
