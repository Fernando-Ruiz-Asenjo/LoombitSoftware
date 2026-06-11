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

from datetime import date
from decimal import Decimal

from ..conciliacion import CENT, Pendiente
from ..expedientes import Expediente, ExpedienteStore

FACTURA_KIND = "factura_intake"


def _importe_factura(fields: dict) -> Decimal | None:
    """Importe que se espera cobrar: total si está, si no base+IVA. None si no hay nada fiable."""
    total = fields.get("total")
    if total is None:
        base, iva = fields.get("base_imponible"), fields.get("iva")
        if base is None or iva is None:
            return None
        total = float(base) + float(iva)
    return Decimal(str(total)).quantize(CENT)


def pendientes_con_vencimiento(store: ExpedienteStore) -> list[tuple[Pendiente, str]]:
    """Como `pendientes_de_cobro`, pero adjunta a cada partida su VENCIMIENTO para poder calcular el
    plan de cobro (Ley 3/2004) sin que el usuario dicte el importe ni la fecha. El vencimiento sale
    del campo `vencimiento`; si falta, de la `fecha` de la factura (NO se inventa un plazo). Devuelve
    `(Pendiente, vencimiento_iso)`; la cadena de vencimiento puede ir vacía si la factura no la trae.
    """
    out: list[tuple[Pendiente, str]] = []
    for exp in store.list(kind=FACTURA_KIND):
        if exp.data.get("sentido") != "devengado" or exp.data.get("cobrado"):
            continue
        fields = exp.data.get("fields", {})
        importe = _importe_factura(fields)
        if importe is None or importe <= 0:
            continue  # sin importe fiable → no se concilia (no inventa)
        pend = Pendiente(
            id=exp.id,
            importe=importe,
            referencia=fields.get("numero") or "",
            contraparte=fields.get("proveedor") or "",
        )
        venc = str(fields.get("vencimiento") or fields.get("fecha") or "")
        out.append((pend, venc))
    return out


def pendientes_de_cobro(store: ExpedienteStore) -> list[Pendiente]:
    """Partidas pendientes de cobro: facturas `devengado` (ventas) aún no marcadas cobradas."""
    return [p for p, _ in pendientes_con_vencimiento(store)]


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
