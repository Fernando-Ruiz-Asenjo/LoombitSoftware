"""
cobros.py — lógica de seguimiento de cobros (Ley 3/2004 de morosidad).

Es el "cerebro" determinista de la cuña 1. Decide, por cada factura, si hay que
reclamar y en qué tono, calculando plazos, compensación e interés con criterio de
administrativo con oficio.

Gates de honestidad (del banco de supuestos):
  - El **tipo de interés de demora es variable** (BCE + 8 puntos, por semestre) y
    NUNCA se inventa: si no se aporta, se marca como "a verificar" (S-02).
  - **Cobro parcial**: se reclama SOLO el saldo pendiente, nunca el total (S-03).
  - **Factura ya cobrada**: no se reclama (S-01).
  - **Vía judicial**: el operador NO la ejecuta; escala a un profesional y, desde
    la L.O. 1/2025, exige intentar antes un MASC (S-02).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

# Compensación fija por costes de cobro (art. 8 Ley 3/2004). Es importe legal fijo.
LATE_FEE_FIXED_EUR = 40.0
# Plazo máximo legal de pago entre empresas (días). Por defecto 30; pacto hasta 60.
MAX_LEGAL_TERM_DAYS = 60


def _to_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    s = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"fecha no reconocida: {value!r}")


def days_overdue(due_date: str | date, today: str | date | None = None) -> int:
    """Días vencidos desde el vencimiento (negativo = aún no vence)."""
    due = _to_date(due_date)
    ref = _to_date(today) if today else date.today()
    return (ref - due).days


def escalation_stage(overdue: int) -> str:
    """
    Etapa de reclamación según días vencidos. Refleja el escalado de un
    administrativo: primero amable, luego firme, luego formal, y solo al final
    la vía judicial (que NO ejecuta el operador).
    """
    if overdue < 0:
        return "por_vencer"
    if overdue == 0:
        return "vence_hoy"
    if overdue <= 7:
        return "recordatorio_amistoso"
    if overdue <= 21:
        return "recordatorio_firme"
    if overdue <= MAX_LEGAL_TERM_DAYS:
        return "reclamacion_formal"
    return "via_judicial"


def late_interest(
    principal: float,
    overdue: int,
    annual_rate_pct: float | None = None,
) -> dict[str, Any]:
    """
    Interés de demora. El tipo (BCE + 8 puntos) es variable por semestre: si no se
    aporta, NO se inventa — se devuelve rate_required=True para verificarlo.
    """
    if overdue <= 0 or principal <= 0:
        return {"amount": 0.0, "rate_required": False, "rate_pct": annual_rate_pct}
    if annual_rate_pct is None:
        return {
            "amount": None,
            "rate_required": True,
            "rate_pct": None,
            "note": (
                "Tipo de interés de demora variable (BCE + 8 puntos, por semestre): "
                "verificar el vigente antes de afirmar un importe."
            ),
        }
    amount = round(principal * (annual_rate_pct / 100.0) * (overdue / 365.0), 2)
    return {"amount": amount, "rate_required": False, "rate_pct": annual_rate_pct}


def dunning_plan(
    *,
    total: float,
    due_date: str | date,
    today: str | date | None = None,
    paid: float = 0.0,
    annual_rate_pct: float | None = None,
) -> dict[str, Any]:
    """
    Plan de cobro de una factura. Devuelve qué hacer, el saldo a reclamar, la etapa
    y los importes legales — respetando los gates (parcial, ya cobrada, judicial).
    """
    outstanding = round(total - paid, 2)
    overdue = days_overdue(due_date, today)

    # Factura ya cobrada por completo → no reclamar (S-01).
    if outstanding <= 0:
        return {
            "action": "no_reclamar",
            "reason": "factura_cobrada",
            "outstanding": 0.0,
            "overdue_days": overdue,
            "stage": "cobrado",
        }

    partial = paid > 0  # cobro parcial → reclamar solo el saldo (S-03)
    stage = escalation_stage(overdue)

    plan: dict[str, Any] = {
        "outstanding": outstanding,
        "overdue_days": overdue,
        "stage": stage,
        "partial_payment": partial,
    }

    if overdue <= 0:
        plan["action"] = "esperar" if overdue < 0 else "preparar_recordatorio"
        return plan

    # Vencida: aplica compensación fija de 40 € e interés (con el gate del tipo).
    plan["action"] = "reclamar"
    plan["fixed_compensation_eur"] = LATE_FEE_FIXED_EUR
    plan["interest"] = late_interest(outstanding, overdue, annual_rate_pct)

    if stage == "via_judicial":
        plan["escalate_to_human"] = True
        plan["requires_masc"] = True
        plan["note"] = (
            "Supera el plazo: la vía judicial la decide un profesional. Desde la "
            "L.O. 1/2025 hay que intentar/documentar un MASC antes de demandar."
        )
    return plan
