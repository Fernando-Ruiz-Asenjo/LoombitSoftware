"""
routers/cobros.py — API del LAZO de cobros de punta a punta (pieza 3 de la fase larga).

GET  /cobros/pendientes  → las decisiones de cobro listas para aprobar (vencidas → decisión). Solo LISTA.
POST /cobros/aprobar     → el humano APRUEBA una cuenta vencida → se envía su recordatorio. Por defecto al
                           outbox local (`via='outbox'`); con `via='gmail'` sale de verdad por Gmail, pero
                           SIEMPRE al DESTINO SEGURO del piloto (§SEG-4), nunca al cliente. El gate de efecto
                           vive dentro: sin esta aprobación no sale nada, y el cuerpo (cifras por código)
                           pasa por el guardia §14B.

Separación de Autoridades: el endpoint no calcula cifras ni redacta con el LLM — orquesta código
determinista (`cobros_flujo`). Llamar a POST /cobros/aprobar con un `cuenta_id` inequívoco ES la
autorización humana (D-20); la decisión y su importe legal los compone `decisions_cobros` por código.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config import get_settings
from ..cuentas_cobrar import CuentasCobrarStore
from ..decisions_cobros import decision_de_cuenta
from ..skill_d_fiscal.cobros_flujo import aprobar_y_enviar, pendientes
from ..skill_d_fiscal.envio_cobro import EnvioBloqueado

router = APIRouter(prefix="/cobros", tags=["cobros"])


class Aprobacion(BaseModel):
    cuenta_id: str
    # "outbox" (local, sin credenciales) | "gmail" (envío real al destino seguro del piloto)
    via: str = "outbox"
    asunto: str = "Recordatorio de pago"


@router.get("/pendientes")
def listar_pendientes() -> dict:
    """Las decisiones de cobro pendientes de aprobar. NO envía nada: solo lista (cada una con su
    cuenta de origen para poder aprobarla)."""
    ds = pendientes(CuentasCobrarStore())
    return {
        "pendientes": [{"cuenta_id": d.source.get("cuenta_id", ""), **d.to_dict()} for d in ds],
        "count": len(ds),
    }


@router.post("/aprobar")
def aprobar(body: Aprobacion) -> dict:
    """El humano aprueba la cuenta `cuenta_id` → se envía su recordatorio. `via='outbox'` (defecto) lo deja
    en el outbox local; `via='gmail'` lo envía de verdad pero SIEMPRE al DESTINO SEGURO del piloto (§SEG-4),
    nunca al cliente. El envío sigue validando dentro (gate de efecto + cifras por código). 404 si la cuenta
    no está vencida o no existe; 422 si el gate bloquea o si `via='gmail'` sin destino seguro configurado.
    """
    store = CuentasCobrarStore()
    cuenta = next((c for c in store.vencidas() if c.id == body.cuenta_id), None)
    if cuenta is None:
        raise HTTPException(
            status_code=404, detail=f"cuenta vencida no encontrada: {body.cuenta_id}"
        )
    decision = decision_de_cuenta(cuenta)
    if decision is None:
        raise HTTPException(
            status_code=404, detail=f"la cuenta {body.cuenta_id} no genera decisión de cobro"
        )
    enviar_fn = None
    destino = "outbox-local"
    if body.via == "gmail":
        # §SEG-4: el destinatario NO es arbitrario — se fuerza al destino seguro del piloto (tu buzón).
        destino = get_settings().cobros_piloto_destino_seguro
        if not destino:
            raise HTTPException(
                status_code=422,
                detail="via='gmail' pero falta el destino seguro: configura "
                "LOOMBIT_OPERATOR_COBROS_PILOTO_DESTINO_SEGURO en .env (§SEG-4).",
            )
        from ..skill_blanca_gmail import send_email

        enviar_fn = send_email
    try:
        recibo = aprobar_y_enviar(
            decision, to_seguro=destino, asunto=body.asunto, enviar_fn=enviar_fn
        )
    except EnvioBloqueado as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"ok": True, "cuenta_id": body.cuenta_id, "recibo": recibo}
