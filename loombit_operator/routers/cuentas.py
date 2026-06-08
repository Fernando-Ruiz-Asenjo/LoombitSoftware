"""
routers/cuentas.py — API de cuentas a cobrar (Fase 2: Morning Brief con datos reales).

GET  /cuentas                 → pendientes + vencidas (con plan de cobro) + próximas + total
GET  /cuentas/{id}/plan       → plan de cobro de una cuenta (saldo, etapa, 40 €, interés con BOE)
POST /cuentas                 → registra una cuenta a cobrar
POST /cuentas/{id}/cobrada    → marca una cuenta como cobrada
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..cobros import dunning_plan
from ..cuentas_cobrar import CuentaCobrar, CuentasCobrarStore

router = APIRouter(prefix="/cuentas", tags=["cuentas-cobrar"])


class NuevaCuenta(BaseModel):
    cliente: str
    importe: float
    vencimiento: str  # ISO date "YYYY-MM-DD"
    concepto: str = ""


def _plan_de(c: CuentaCobrar) -> dict:
    """Plan de cobro determinista de una cuenta (saldo, etapa, compensación e interés con cita BOE)."""
    return dunning_plan(total=c.importe, due_date=c.vencimiento)


@router.get("")
def listar() -> dict:
    s = CuentasCobrarStore()
    pend = s.pendientes()
    return {
        "pendientes": [c.to_dict() for c in pend],
        # cada vencida trae su plan de cobro ya calculado (lo que el operador puede reclamar).
        "vencidas": [{**c.to_dict(), "plan": _plan_de(c)} for c in s.vencidas()],
        "proximas": [c.to_dict() for c in s.proximas(7)],
        "total_pendiente": round(sum(c.importe for c in pend), 2),
    }


@router.get("/{cuenta_id}/plan")
def plan(cuenta_id: str) -> dict:
    s = CuentasCobrarStore()
    c = next((x for x in s.list() if x.id == cuenta_id), None)
    if c is None:
        raise HTTPException(status_code=404, detail=f"cuenta no encontrada: {cuenta_id}")
    return {**c.to_dict(), "plan": _plan_de(c)}


@router.post("")
def crear(body: NuevaCuenta) -> dict:
    s = CuentasCobrarStore()
    c = s.add(
        CuentaCobrar(
            cliente=body.cliente,
            importe=body.importe,
            vencimiento=body.vencimiento,
            concepto=body.concepto,
        )
    )
    return c.to_dict()


@router.post("/{cuenta_id}/cobrada")
def cobrada(cuenta_id: str) -> dict:
    s = CuentasCobrarStore()
    if not s.marcar_cobrada(cuenta_id):
        raise HTTPException(status_code=404, detail=f"cuenta no encontrada: {cuenta_id}")
    return {"ok": True, "id": cuenta_id, "estado": "cobrada"}
