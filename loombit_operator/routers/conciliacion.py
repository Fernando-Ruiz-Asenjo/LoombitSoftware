"""
routers/conciliacion.py — API de conciliación bancaria, multi-entidad.

Flujo en dos pasos con **el humano en el bucle** (regla nº1: la IA propone, no decide el dinero):

1. `POST /entidades/{id}/conciliacion` — sube un extracto Norma 43, lo parsea (con cuadre del
   registro 33), casa los abonos contra las facturas pendientes de cobro con semáforo de
   confianza y abre un Expediente `conciliacion_bancaria` en `PENDING_APPROVAL`. **No marca
   nada como cobrado**: devuelve la propuesta para que el humano la revise.
2. `POST /entidades/{id}/conciliacion/{exp_id}/aprobar` — el humano confirma qué matches
   aplicar; solo entonces se marcan las facturas como cobradas (alimenta el gate S-01 de
   cobros) y se cierra el expediente con traza inmutable.

Determinista y local: ningún número lo pone un LLM. Si el extracto no cuadra, el aviso viaja
en la propuesta y el humano decide.
"""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..conciliacion import Conciliacion, ConfianzaTier, Movimiento, conciliar, parse_norma43
from ..expedientes import (
    ExpedienteNotFoundError,
    ExpedienteStatus,
    ExpedienteStore,
)
from ..skill_d_fiscal import marcar_cobrada, pendientes_de_cobro

router = APIRouter(prefix="/entidades", tags=["conciliacion"])

CONCILIACION_KIND = "conciliacion_bancaria"


class ConciliarIn(BaseModel):
    formato: str = "n43"  # por ahora solo Norma 43; CSV documentado como siguiente paso
    contenido: str


class MatchConfirmado(BaseModel):
    movimiento_idx: int
    factura_id: str
    parcial: bool = False


class AprobarConciliacionIn(BaseModel):
    matches: list[MatchConfirmado]
    actor: str = "human"


def _store(entity_id: str) -> ExpedienteStore:
    try:
        return ExpedienteStore(entity_id=entity_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _serializar(idx: int, c: Conciliacion) -> dict:
    mov = c.movimiento
    return {
        "idx": idx,
        "fecha": mov.fecha_operacion.isoformat(),
        "importe": str(mov.importe),
        "concepto": mov.texto,
        "tier": c.tier.value,
        "razon": c.razon,
        "score": c.score,
        "factura_id": c.pendiente.id if c.pendiente else None,
        "factura_referencia": c.pendiente.referencia if c.pendiente else None,
        "grupo_ids": [p.id for p in c.grupo],
    }


def _banco_ref(mov: Movimiento, idx: int) -> str:
    return f"extracto mov#{idx} {mov.fecha_operacion.isoformat()} {mov.texto[:40]}".strip()


@router.post("/{entity_id}/conciliacion")
def proponer_conciliacion(entity_id: str, body: ConciliarIn) -> dict:
    if body.formato != "n43":
        raise HTTPException(
            status_code=400,
            detail=f"formato no soportado: {body.formato!r} (por ahora solo 'n43')",
        )
    cuentas = parse_norma43(body.contenido)
    if not cuentas:
        raise HTTPException(status_code=400, detail="el extracto Norma 43 no contiene cuentas")

    store = _store(entity_id)
    pendientes = pendientes_de_cobro(store)

    movimientos: list[Movimiento] = [m for c in cuentas for m in c.movimientos]
    conciliaciones = conciliar(movimientos, pendientes)
    propuesta = [_serializar(i, c) for i, c in enumerate(conciliaciones)]

    avisos_cuadre = [a for c in cuentas for a in c.avisos]
    resumen = {t.value: sum(1 for c in conciliaciones if c.tier is t) for t in ConfianzaTier}

    exp = store.create(
        CONCILIACION_KIND,
        f"Conciliación bancaria · {len(movimientos)} movimientos",
        data={
            "cuentas": [{"entidad": c.entidad, "cuenta": c.cuenta} for c in cuentas],
            "avisos_cuadre": avisos_cuadre,
            "resumen_tiers": resumen,
            "propuesta": propuesta,
            "pendientes_evaluadas": len(pendientes),
        },
    )
    store.set_status(exp.id, ExpedienteStatus.PENDING_APPROVAL)
    return {
        "expediente_id": exp.id,
        "status": ExpedienteStatus.PENDING_APPROVAL.value,
        "resumen_tiers": resumen,
        "avisos_cuadre": avisos_cuadre,
        "propuesta": propuesta,
    }


@router.post("/{entity_id}/conciliacion/{expediente_id}/aprobar")
def aprobar_conciliacion(entity_id: str, expediente_id: str, body: AprobarConciliacionIn) -> dict:
    """El humano confirma qué matches aplicar. Solo esos marcan factura como cobrada; el resto
    queda sin conciliar (no se inventa). Cierra el expediente con traza inmutable."""
    store = _store(entity_id)
    try:
        exp = store.get(expediente_id)
    except ExpedienteNotFoundError as exc:
        raise HTTPException(status_code=404, detail="expediente no encontrado") from exc
    if exp.kind != CONCILIACION_KIND:
        raise HTTPException(status_code=400, detail="el expediente no es de conciliación bancaria")

    propuesta = {p["idx"]: p for p in exp.data.get("propuesta", [])}
    aplicados: list[dict] = []
    for m in body.matches:
        prop = propuesta.get(m.movimiento_idx)
        if prop is None:
            raise HTTPException(
                status_code=400, detail=f"movimiento_idx {m.movimiento_idx} no está en la propuesta"
            )
        try:
            factura = marcar_cobrada(
                store,
                m.factura_id,
                importe_cobrado=Decimal(prop["importe"]),
                banco_ref=f"{CONCILIACION_KIND}:{expediente_id} mov#{m.movimiento_idx}",
                fecha_cobro=prop["fecha"],
                parcial=m.parcial,
                actor=body.actor,
            )
        except ExpedienteNotFoundError as exc:
            raise HTTPException(
                status_code=404, detail=f"factura {m.factura_id} no encontrada"
            ) from exc
        store.add_event(
            expediente_id,
            "match_confirmado",
            {
                "movimiento_idx": m.movimiento_idx,
                "factura_id": m.factura_id,
                "importe": prop["importe"],
                "parcial": m.parcial,
            },
            body.actor,
        )
        aplicados.append({"movimiento_idx": m.movimiento_idx, "factura_id": factura.id})

    cerrado = store.set_status(expediente_id, ExpedienteStatus.CLOSED, body.actor)
    return {
        "expediente_id": cerrado.id,
        "status": cerrado.status.value,
        "matches_aplicados": aplicados,
        "trazabilidad_integra": store.verify_chain(expediente_id),
    }
