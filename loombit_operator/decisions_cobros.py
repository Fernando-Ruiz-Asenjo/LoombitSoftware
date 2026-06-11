"""
decisions_cobros.py — LD-2 de «Loombit Decide»: el compositor de DECISIONES de cobro (Skill D).

La rebanada vertical: el cerebro detecta el impago (esto ya existe: `cobros.dunning_plan` sobre las
cuentas vencidas) → se compone **una decisión** por cobro, con su plan legal (Ley 3/2004) ya
calculado por CÓDIGO, su porqué y su acción preparada → entra en la COLA (LD-0). Cuando el humano la
APRUEBA, se lanza la tarea preparada al agente y el **gate de efecto** retiene el envío (LD-1/gate).

Separación de Autoridades: las cifras (saldo, 40 € art. 8, interés de demora con su tipo BOE) las
pone `cobros.py` determinista; el LLM no interviene aquí. El `payload.agent_task` es texto preparado;
el envío real NO sale de aquí — pasa por el agente y su gate `PENDING_APPROVAL`.

Dominio (cobros) fuera del núcleo blanco: vive en su módulo, no en `decisions.py`.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from .cobros import dunning_plan
from .decisions import Decision, DecisionKind, DecisionOption, OptionKind, Risk

# Tono de la reclamación según la etapa de escalado (igual criterio que el telar).
_TONO_ETAPA = {
    "vence_hoy": "cordial",
    "recordatorio_amistoso": "cordial",
    "recordatorio_firme": "firme pero cordial",
    "reclamacion_formal": "formal",
}


def _eur(x: float) -> str:
    """1302.86 → '1.302,86' (formato español)."""
    s = f"{float(x or 0):,.2f}"
    return s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def _detalle_legal(plan: dict[str, Any]) -> tuple[str, float]:
    """Desglose honesto del plan (saldo + compensación + interés) y el total reclamable. Cifras del
    plan determinista; si el interés cae fuera de la tabla BOE, se dice 'a verificar' (no se inventa).
    """
    saldo = plan.get("outstanding", 0) or 0
    fee = plan.get("fixed_compensation_eur", 0) or 0
    interes = plan.get("interest", {}) or {}
    int_amt = interes.get("amount") or 0
    partes = [f"Saldo {_eur(saldo)} € + {_eur(fee)} € comp. (art. 8)"]
    if interes.get("rate_required"):
        partes.append("+ interés de demora a verificar (fuera de la tabla BOE)")
    elif int_amt:
        partes.append(f"+ {_eur(int_amt)} € interés demora (Ley 3/2004)")
    reclamable = round(float(saldo) + float(fee) + float(int_amt), 2)
    return " ".join(partes) + f" → reclamable ≈ {_eur(reclamable)} €.", reclamable


def decision_de_cuenta(cuenta: Any, today: str | date | None = None) -> Decision | None:
    """Compone la `Decision` de cobro de una cuenta vencida. Devuelve None si no procede reclamar
    (cobrada, aún no vencida): no se sube al humano una decisión vacía."""
    importe = getattr(cuenta, "importe", 0) or 0
    cliente = getattr(cuenta, "cliente", "") or ""
    venc = getattr(cuenta, "vencimiento", "") or ""
    if not venc:
        return None
    hoy = today.isoformat() if isinstance(today, date) else today
    plan = dunning_plan(total=float(importe), due_date=venc, today=hoy)
    if plan.get("action") != "reclamar":
        return None  # no vencida / cobrada → no es una decisión

    dias = plan["overdue_days"]
    stage = plan["stage"]
    detalle, _reclamable = _detalle_legal(plan)
    tono = _TONO_ETAPA.get(stage, "cordial")
    judicial = stage == "via_judicial"

    if judicial:
        task = (
            f"La factura vencida de {cliente} por {importe:.0f} € supera el plazo (vencida hace "
            f"{dias} días). Prepárame un resumen para escalar la vía judicial a un profesional; "
            "recuerda que desde la L.O. 1/2025 hay que intentar/documentar un MASC antes de demandar. "
            "No envíes nada todavía."
        )
        label_aprobar = "Escalar a un profesional"
        why = f"Vencida hace {dias} días — supera el plazo; conviene escalarlo."
        risk = Risk.ALTO
    else:
        task = (
            f"Prepara un recordatorio de cobro {tono} para {cliente} por {importe:.0f} € "
            f"(factura vencida hace {dias} días; saldo {_eur(plan['outstanding'])} €). "
            "Hazlo en mi nombre, claro y respetuoso. No lo envíes sin que lo apruebe."
        )
        label_aprobar = "Aprobar y enviar"
        why = f"Vencida hace {dias} días — el recordatorio ya está redactado."
        risk = Risk.MEDIO

    return Decision(
        title=f"{cliente} · {importe:.0f} € VENCIDA ({dias}d)",
        why=why,
        detail=detalle,
        kind=DecisionKind.COBRO,
        risk=risk,
        reversible=True,  # un recordatorio/resumen es reversible; el envío real lo retiene el gate
        options=[
            DecisionOption(id="aprobar", label=label_aprobar, kind=OptionKind.APROBAR),
            DecisionOption(id="editar", label="Editar", kind=OptionKind.EDITAR),
            DecisionOption(id="posponer", label="Posponer", kind=OptionKind.POSPONER),
        ],
        payload={
            "cliente": cliente,
            "importe": float(importe),
            "plan": plan,
            "agent_task": task,  # texto preparado; el envío pasa por el agente + su gate
        },
        source={"cuenta_id": getattr(cuenta, "id", ""), "tipo": "cobro_vencido"},
    )


def decisiones_de_cobros(vencidas: list[Any], today: str | date | None = None) -> list[Decision]:
    """Compone las decisiones de cobro de una lista de cuentas vencidas (omite las que no procede)."""
    out: list[Decision] = []
    for c in vencidas:
        d = decision_de_cuenta(c, today)
        if d is not None:
            out.append(d)
    return out
