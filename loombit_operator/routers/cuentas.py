"""
routers/cuentas.py — API de cuentas a cobrar (Fase 2: Morning Brief con datos reales).

GET  /cuentas                 → pendientes + vencidas + próximas + total pendiente
POST /cuentas                 → registra una cuenta a cobrar
POST /cuentas/{id}/cobrada    → marca una cuenta como cobrada
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..cuentas_cobrar import CuentaCobrar, CuentasCobrarStore

router = APIRouter(prefix="/cuentas", tags=["cuentas-cobrar"])


class NuevaCuenta(BaseModel):
    cliente: str
    importe: float
    vencimiento: str  # ISO date "YYYY-MM-DD"
    concepto: str = ""


@router.get("")
def listar() -> dict:
    s = CuentasCobrarStore()
    pend = s.pendientes()
    return {
        "pendientes": [c.to_dict() for c in pend],
        "vencidas": [c.to_dict() for c in s.vencidas()],
        "proximas": [c.to_dict() for c in s.proximas(7)],
        "total_pendiente": round(sum(c.importe for c in pend), 2),
    }


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
