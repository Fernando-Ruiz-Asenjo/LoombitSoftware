"""
routers/fiscal.py — API de Expedientes + Skill D Fiscal (303), multi-entidad.

La IA prepara; el humano valida y presenta. **Ningún endpoint presenta a la AEAT ni marca
algo como presentado sin justificante.** El 303 se calcula y queda PENDING_APPROVAL; el
humano lo cierra aportando el justificante. Ver `docs/PLATAFORMA_FISCAL_ANALISIS.md`.
"""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..docs_intel import InvoiceFields
from ..expedientes import (
    Expediente,
    ExpedienteNotFoundError,
    ExpedienteStatus,
    ExpedienteStore,
)
from ..skill_d_fiscal import liquidar_303_periodo, registrar_factura

router = APIRouter(prefix="/entidades", tags=["fiscal"])


class FacturaIn(BaseModel):
    sentido: str  # "devengado" (emitida/venta) | "soportado" (recibida/compra)
    numero: str | None = None
    proveedor: str | None = None
    base_imponible: float | None = None
    iva: float | None = None
    total: float | None = None
    vencimiento: str | None = None  # ISO; si falta y es emitida → plazo estándar (30 días)


class FacturaDocIn(BaseModel):
    sentido: str  # "devengado" (emitida) | "soportado" (recibida)
    text: str = ""  # texto de la factura (cuerpo de correo o ya extraído)
    path: str = ""  # o la ruta a un PDF local (se extrae aquí)


class Liquidar303In(BaseModel):
    periodo: str


class AprobarIn(BaseModel):
    justificante: str | None = None
    actor: str = "human"


def _store(entity_id: str) -> ExpedienteStore:
    try:
        return ExpedienteStore(entity_id=entity_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _summary(exp: Expediente) -> dict:
    return {
        "id": exp.id,
        "kind": exp.kind,
        "title": exp.title,
        "status": exp.status.value,
        "created_at": exp.created_at,
    }


@router.get("/{entity_id}/expedientes")
def list_expedientes(entity_id: str, kind: str | None = None) -> dict:
    store = _store(entity_id)
    exps = store.list(kind=kind)
    return {"entity_id": entity_id, "count": len(exps), "expedientes": [_summary(e) for e in exps]}


@router.get("/{entity_id}/expedientes/{expediente_id}")
def get_expediente(entity_id: str, expediente_id: str) -> dict:
    store = _store(entity_id)
    try:
        exp = store.get(expediente_id)
    except ExpedienteNotFoundError as exc:
        raise HTTPException(status_code=404, detail="expediente no encontrado") from exc
    return {
        "expediente": {**_summary(exp), "data": exp.data},
        "trazabilidad_integra": store.verify_chain(expediente_id),
        "eventos": [asdict(e) for e in store.events(expediente_id)],
        "documentos": [asdict(d) for d in store.documents(expediente_id)],
    }


@router.post("/{entity_id}/facturas")
def add_factura(entity_id: str, body: FacturaIn) -> dict:
    store = _store(entity_id)
    inv = InvoiceFields(
        numero=body.numero,
        proveedor=body.proveedor,
        base_imponible=body.base_imponible,
        iva=body.iva,
        total=body.total,
    )
    exp = registrar_factura(store, inv, body.sentido)

    # Factura EMITIDA (venta) → alimenta el store de cuentas a cobrar (Fase 2, automático).
    from ..cuentas_cobrar import CuentasCobrarStore, cuenta_desde_factura

    cuenta = cuenta_desde_factura(
        proveedor=body.proveedor,
        total=body.total,
        sentido=body.sentido,
        numero=body.numero or "",
        vencimiento=body.vencimiento,
    )
    if cuenta:
        CuentasCobrarStore().add(cuenta)

    return _summary(exp)


@router.post("/{entity_id}/facturas/desde-documento")
def add_factura_desde_documento(entity_id: str, body: FacturaDocIn) -> dict:
    """Intake real: de una factura (texto de correo o PDF en `path`) AL registro para el 303.
    Extrae los campos con el extractor determinista y registra el expediente. No inventa: si no es
    legible, registra y avisa. Si es emitida y tiene total, alimenta cuentas a cobrar."""
    from ..skill_d_fiscal import registrar_factura_desde_texto

    store = _store(entity_id)
    texto = body.text
    if not texto and body.path:
        from ..docs_intel import extract_text_from_pdf

        info = extract_text_from_pdf(body.path)
        if info.get("error"):
            raise HTTPException(status_code=400, detail=info["error"])
        texto = info.get("text", "")
    if not texto:
        raise HTTPException(status_code=400, detail="Indica `text` o `path` de la factura.")

    exp, inv, avisos = registrar_factura_desde_texto(store, texto, body.sentido)

    # Factura EMITIDA con total → alimenta cuentas a cobrar (igual que el alta manual).
    from ..cuentas_cobrar import CuentasCobrarStore, cuenta_desde_factura

    cuenta = cuenta_desde_factura(
        proveedor=inv.proveedor,
        total=inv.total,
        sentido=body.sentido,
        numero=inv.numero or "",
        vencimiento=inv.vencimiento,
    )
    if cuenta:
        CuentasCobrarStore().add(cuenta)

    return {**_summary(exp), "campos": inv.to_dict(), "avisos": avisos}


@router.post("/{entity_id}/303")
def liquidar_303(entity_id: str, body: Liquidar303In) -> dict:
    store = _store(entity_id)
    exp, res = liquidar_303_periodo(store, body.periodo)
    return {
        "expediente_id": exp.id,
        "status": exp.status.value,  # pending_approval: la IA NO presenta
        "resultado": str(res.resultado),
        "casillas": res.casillas,
        "avisos": res.avisos,
        "borrador": exp.data.get("borrador"),
    }


@router.post("/{entity_id}/expedientes/{expediente_id}/aprobar")
def aprobar(entity_id: str, expediente_id: str, body: AprobarIn) -> dict:
    """El humano confirma revisión/presentación. Con justificante → se adjunta su referencia
    y se cierra; sin él → queda en revisión. La IA nunca cierra sola sin esta acción humana."""
    store = _store(entity_id)
    try:
        store.get(expediente_id)
    except ExpedienteNotFoundError as exc:
        raise HTTPException(status_code=404, detail="expediente no encontrado") from exc
    if body.justificante:
        store.add_event(
            expediente_id, "justificante_aportado", {"ref": body.justificante}, body.actor
        )
        exp = store.set_status(expediente_id, ExpedienteStatus.CLOSED, body.actor)
    else:
        exp = store.set_status(expediente_id, ExpedienteStatus.IN_REVIEW, body.actor)
    return _summary(exp)
