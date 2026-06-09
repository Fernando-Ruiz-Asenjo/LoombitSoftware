"""
Tools de DOMINIO administrativo — exponen los "cerebros" deterministas que ya
existían como módulos (cobros, fiscal 303) como herramientas que el AGENTE puede
invocar. Antes el chat anunciaba "Reclamar cobro" / "303" pero el agente no tenía
ninguna tool para hacerlo → 0 steps y narración vacía. Esto le da las manos.

Local-first y determinista: el cálculo lo hace código (no el LLM); el LLM solo
decide cuándo llamar y narra el resultado. Ningún efecto externo aquí (no envían
nada): preparar un cobro o un borrador de 303 es seguro; el envío real sigue
pasando por gmail_send con su gate.
"""

from __future__ import annotations

from typing import Any

from ..cobros import LATE_FEE_FIXED_EUR, dunning_plan
from ..skill_d_fiscal.modelo_303 import LineaIVA, borrador_303_texto, calcular_303
from .registry import ToolDefinition, tool_registry

_STAGE_ES = {
    "por_vencer": "aún no vence",
    "vence_hoy": "vence hoy",
    "recordatorio_amistoso": "recordatorio amistoso (1–7 días vencida)",
    "recordatorio_firme": "recordatorio firme (8–21 días)",
    "reclamacion_formal": "reclamación formal (22–60 días)",
    "via_judicial": "vía judicial (>60 días) — la decide un profesional",
    "cobrado": "cobrado",
}


def _plan_cobro(
    total: float,
    fecha_vencimiento: str,
    cobrado: float = 0.0,
    tipo_interes_anual: float | None = None,
) -> str:
    """Calcula el plan de cobro de UNA factura (Ley 3/2004): saldo, etapa, interés y compensación."""
    try:
        plan: dict[str, Any] = dunning_plan(
            total=float(total),
            due_date=str(fecha_vencimiento),
            paid=float(cobrado or 0),
            annual_rate_pct=tipo_interes_anual,
        )
    except (ValueError, TypeError) as exc:
        return f"ERROR: no pude calcular el cobro ({exc}). Dame el total y la fecha de vencimiento."

    accion = plan.get("action")
    if accion == "no_reclamar":
        return "Esta factura ya está cobrada por completo: no hay nada que reclamar."

    saldo = plan.get("outstanding")
    overdue = plan.get("overdue_days", 0)
    etapa = _STAGE_ES.get(str(plan.get("stage")), str(plan.get("stage")))

    partes = [f"Saldo pendiente: {saldo} €."]
    if overdue < 0:
        partes.append(
            f"Aún no vence (faltan {abs(overdue)} días). Acción: esperar / preparar aviso."
        )
    elif accion == "preparar_recordatorio":
        partes.append("Vence hoy. Acción: preparar recordatorio amistoso.")
    else:
        partes.append(f"Vencida hace {overdue} días → {etapa}.")
        partes.append(
            f"Compensación legal por costes de cobro (art. 8): {LATE_FEE_FIXED_EUR:.0f} €."
        )
        interes = plan.get("interest") or {}
        if interes.get("rate_required"):
            partes.append(
                "Interés de demora: tipo variable (BCE + 8, por semestre) — a verificar el vigente."
            )
        elif interes.get("amount") is not None:
            rate = interes.get("rate_pct")
            cita = interes.get("fuente") or interes.get("note") or ""
            txt = f"Interés de demora: {interes['amount']} €"
            if rate:
                txt += f" (al {rate}% anual)"
            partes.append(txt + (f". {cita}" if cita else "."))
        if plan.get("escalate_to_human"):
            partes.append(
                "Supera el plazo: la vía judicial la decide un profesional; desde la "
                "L.O. 1/2025 hay que intentar/documentar un MASC antes de demandar."
            )
        partes.append("Acción recomendada: redactar la reclamación (te la dejo lista para enviar).")
    return " ".join(partes)


def _norm_tipo(t: object) -> float:
    """Acepta 21, 21.0 o 0.21 y devuelve fracción (0.21)."""
    v = float(t)
    return v / 100.0 if v > 1 else v


def _calcular_303(
    iva_repercutido: list[dict] | None = None,
    iva_soportado: list[dict] | None = None,
    periodo: str = "",
) -> str:
    """Calcula un BORRADOR del modelo 303 (IVA, régimen general) a partir de bases y tipos."""
    lineas: list[LineaIVA] = []
    try:
        for it in iva_repercutido or []:
            lineas.append(
                LineaIVA(
                    base=it["base"],
                    tipo=_norm_tipo(it.get("tipo", 0.21)),
                    sentido="devengado",
                    concepto=str(it.get("concepto", "venta")),
                )
            )
        for it in iva_soportado or []:
            lineas.append(
                LineaIVA(
                    base=it["base"],
                    tipo=_norm_tipo(it.get("tipo", 0.21)),
                    sentido="soportado",
                    concepto=str(it.get("concepto", "compra")),
                )
            )
    except (KeyError, TypeError, ValueError) as exc:
        return (
            "ERROR: necesito las líneas de IVA como listas de {base, tipo} "
            f"para ventas (repercutido) y compras (soportado). Detalle: {exc}"
        )
    if not lineas:
        return (
            "Para el 303 necesito al menos las bases de tus ventas (IVA repercutido) y, si las "
            "hay, de tus compras (IVA soportado). Dímelas y te dejo el borrador."
        )
    res = calcular_303(lineas)
    return borrador_303_texto(res, periodo or "periodo indicado")


tool_registry.register(
    ToolDefinition(
        name="plan_cobro",
        description=(
            "Calcula el plan de cobro de UNA factura impagada o vencida según la Ley 3/2004 "
            "de morosidad: saldo pendiente, días vencidos, etapa de reclamación, compensación "
            "legal de 40 € e interés de demora (tipo legal del BOE). Úsala cuando el usuario "
            "quiera reclamar un cobro o saber cómo está una factura pendiente. NO envía nada."
        ),
        parameters={
            "type": "object",
            "properties": {
                "total": {"type": "number", "description": "Importe total de la factura (€)."},
                "fecha_vencimiento": {
                    "type": "string",
                    "description": "Fecha de vencimiento (YYYY-MM-DD o DD/MM/YYYY).",
                },
                "cobrado": {
                    "type": "number",
                    "description": "Importe ya cobrado (€). 0 si nada.",
                    "default": 0,
                },
                "tipo_interes_anual": {
                    "type": "number",
                    "description": "Tipo de interés de demora anual en %, si se conoce. "
                    "Si se omite, se usa el tipo legal del BOE.",
                },
            },
            "required": ["total", "fecha_vencimiento"],
        },
        fn=_plan_cobro,
        category="base",
    )
)

tool_registry.register(
    ToolDefinition(
        name="calcular_303",
        description=(
            "Calcula un BORRADOR del modelo 303 (IVA trimestral, régimen general) a partir de "
            "las bases imponibles y tipos de tus facturas emitidas (IVA repercutido) y recibidas "
            "(IVA soportado). Devuelve IVA devengado, deducible y resultado a ingresar/compensar. "
            "Es un borrador, NO una presentación. Úsala para el 303 / IVA del trimestre."
        ),
        parameters={
            "type": "object",
            "properties": {
                "iva_repercutido": {
                    "type": "array",
                    "description": "Ventas emitidas: lista de {base, tipo}. tipo en % (21) o fracción (0.21).",
                    "items": {
                        "type": "object",
                        "properties": {
                            "base": {"type": "number"},
                            "tipo": {"type": "number"},
                            "concepto": {"type": "string"},
                        },
                        "required": ["base"],
                    },
                },
                "iva_soportado": {
                    "type": "array",
                    "description": "Compras recibidas deducibles: lista de {base, tipo}.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "base": {"type": "number"},
                            "tipo": {"type": "number"},
                            "concepto": {"type": "string"},
                        },
                        "required": ["base"],
                    },
                },
                "periodo": {
                    "type": "string",
                    "description": "Periodo, p.ej. '2T 2026'.",
                },
            },
        },
        fn=_calcular_303,
        category="base",
    )
)
