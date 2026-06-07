"""
Router — Skill Blanca Actions.
Ejecuta acciones reales: enviar email, crear evento de calendario.

Endpoints:
  POST /skill-blanca/actions/gmail/send
  POST /skill-blanca/actions/calendar/create
  GET  /skill-blanca/actions/outbox            → lista recibos locales

Todos los endpoints validan:
  1. Que el conector está habilitado (CONNECTOR_WRITES_ENABLED=true)
  2. Que hay token OAuth activo para Google
  3. Que los parámetros son válidos

🟡 Estado: contrato implementado. Pendiente piloto real (Fase 1).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field

from ..config import get_settings
from ..skill_blanca_calendar import (
    create_event,
    snapshot_calendar_outbox,
)
from ..skill_blanca_gmail import send_email, snapshot_outbox

router = APIRouter(prefix="/skill-blanca/actions", tags=["skill-blanca-actions"])


# ── Request models ────────────────────────────────────────────────────────────


class GmailSendRequest(BaseModel):
    to: EmailStr
    subject: str = Field(..., min_length=1, max_length=500)
    body_text: str = Field(..., min_length=1)
    body_html: str | None = None
    cc: str = ""
    reply_to: str = ""


class CalendarCreateRequest(BaseModel):
    summary: str = Field(..., min_length=1, max_length=500)
    start_iso: str = Field(..., description="ISO 8601: '2025-06-10T10:00:00' o '2025-06-10'")
    end_iso: str | None = None
    duration_minutes: int = Field(default=60, gt=0, le=1440)
    description: str = ""
    location: str = ""
    attendees: list[str] = Field(default_factory=list)
    timezone: str = "Europe/Madrid"
    all_day: bool = False
    calendar_id: str = "primary"


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/gmail/send")
def action_gmail_send(req: GmailSendRequest) -> dict[str, Any]:
    """
    Envía un email via Gmail API.
    Requiere: Google OAuth conectado + CONNECTOR_WRITES_ENABLED=true en .env

    Returns:
        receipt con message_id, thread_id, receipt_path y metadatos.
        El recibo queda guardado en runtime/local/outbox/.
    """
    settings = get_settings()
    try:
        receipt = send_email(
            to=str(req.to),
            subject=req.subject,
            body_text=req.body_text,
            body_html=req.body_html,
            cc=req.cc,
            reply_to=req.reply_to,
            settings=settings,
        )
    except ValueError as exc:
        _raise_action_error(str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Gmail API error: {exc}") from exc
    return receipt


@router.post("/calendar/create")
def action_calendar_create(req: CalendarCreateRequest) -> dict[str, Any]:
    """
    Crea un evento en Google Calendar.
    Requiere: Google OAuth conectado + CONNECTOR_WRITES_ENABLED=true en .env

    Returns:
        receipt con event_id, html_link, receipt_path, ics_path y metadatos.
        El recibo queda guardado en runtime/local/outbox/.
    """
    settings = get_settings()
    try:
        receipt = create_event(
            summary=req.summary,
            start_iso=req.start_iso,
            end_iso=req.end_iso,
            duration_minutes=req.duration_minutes,
            description=req.description,
            location=req.location,
            attendees=req.attendees,
            timezone=req.timezone,
            all_day=req.all_day,
            calendar_id=req.calendar_id,
            settings=settings,
        )
    except ValueError as exc:
        _raise_action_error(str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Calendar API error: {exc}") from exc
    return receipt


@router.get("/outbox")
def action_outbox() -> dict[str, Any]:
    """
    Lista los últimos recibos de acciones ejecutadas (emails + eventos).
    Solo lectura — no ejecuta nada.
    """
    settings = get_settings()
    gmail_snap = snapshot_outbox(settings)
    cal_snap = snapshot_calendar_outbox(settings)
    return {
        "gmail": gmail_snap,
        "calendar": cal_snap,
        "total": gmail_snap["count"] + cal_snap["count"],
        "safety_contract": {
            "local_only": True,
            "receipts_never_deleted_automatically": True,
        },
    }


# ── Helpers ───────────────────────────────────────────────────────────────────


def _raise_action_error(detail: str) -> None:
    if "no_token" in detail or "no está conectado" in detail:
        raise HTTPException(status_code=403, detail=detail)
    if "disabled" in detail or "deshabilitad" in detail:
        raise HTTPException(status_code=403, detail=detail)
    raise HTTPException(status_code=400, detail=detail)
