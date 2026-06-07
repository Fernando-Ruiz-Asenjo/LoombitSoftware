"""
Skill Blanca — Google Calendar creator.
Crea eventos en Google Calendar via API REST usando el access_token OAuth.
Guarda recibo local en runtime/local/outbox/ (.json + .ics).

🟡 Estado: contrato implementado. Pendiente piloto real contra cuenta de prueba (Fase 1).
   Para pasar a 🟢: ejecutar create_event() con token real y verificar recibo guardado.

Flujo:
  1. load_access_token("google") → token del store local
  2. compose_event()             → payload JSON para Calendar API
  3. create_event()              → POST a Calendar API, guarda recibo + .ics
  4. recibo devuelto             → { event_id, html_link, receipt_path, ics_path, ... }
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

import httpx

from .config import AppSettings, get_settings
from .skill_blanca_oauth import load_access_token

CALENDAR_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
DEFAULT_CALENDAR = "primary"


# ── Composición de evento ─────────────────────────────────────────────────────


def compose_event(
    *,
    summary: str,
    start_iso: str,
    end_iso: str | None = None,
    duration_minutes: int = 60,
    description: str = "",
    location: str = "",
    attendees: list[str] | None = None,
    timezone: str = "Europe/Madrid",
    all_day: bool = False,
) -> dict[str, Any]:
    """
    Construye el payload para Google Calendar API v3.
    Acepta fechas ISO 8601: "2025-06-10T10:00:00" o "2025-06-10" (all_day=True).

    Returns:
        dict listo para pasar a create_event() como `event_payload`.
    """
    if not summary.strip():
        raise ValueError("calendar_event_summary_required")
    if not start_iso.strip():
        raise ValueError("calendar_event_start_required")

    if all_day:
        start_date = start_iso[:10]
        end_date = end_iso[:10] if end_iso else start_date
        time_block = {
            "start": {"date": start_date},
            "end": {"date": end_date},
        }
    else:
        start_dt = _parse_dt(start_iso)
        if end_iso:
            end_dt = _parse_dt(end_iso)
        else:
            end_dt = start_dt + timedelta(minutes=duration_minutes)
        time_block = {
            "start": {"dateTime": start_dt.isoformat(), "timeZone": timezone},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": timezone},
        }

    payload: dict[str, Any] = {"summary": summary, **time_block}

    if description:
        payload["description"] = description
    if location:
        payload["location"] = location
    if attendees:
        payload["attendees"] = [{"email": e.strip()} for e in attendees if e.strip()]

    return payload


def create_event(
    *,
    summary: str,
    start_iso: str,
    end_iso: str | None = None,
    duration_minutes: int = 60,
    description: str = "",
    location: str = "",
    attendees: list[str] | None = None,
    timezone: str = "Europe/Madrid",
    all_day: bool = False,
    calendar_id: str = DEFAULT_CALENDAR,
    settings: AppSettings | None = None,
    http_post: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """
    Crea el evento en Google Calendar y guarda recibo local (.json + .ics).

    Returns:
        receipt — dict con event_id, html_link, receipt_path, ics_path y metadatos.
    """
    active = settings or get_settings()
    _check_writes_enabled(active)

    token = load_access_token(active.skill_blanca_oauth_token_store_path, "google")
    if not token:
        raise ValueError(
            "calendar_create_no_token: Google OAuth no está conectado. "
            "Ejecuta /skill-blanca/oauth/google/start primero."
        )

    event_payload = compose_event(
        summary=summary,
        start_iso=start_iso,
        end_iso=end_iso,
        duration_minutes=duration_minutes,
        description=description,
        location=location,
        attendees=attendees,
        timezone=timezone,
        all_day=all_day,
    )

    url = CALENDAR_EVENTS_URL.format(calendar_id=calendar_id)
    post = http_post or httpx.post
    resp = post(
        url,
        json=event_payload,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=20,
    )

    if resp.status_code == 401:
        raise ValueError(
            "calendar_create_unauthorized: El token de Google ha expirado. "
            "Ejecuta /skill-blanca/oauth/google/start para reconectar."
        )
    if not (200 <= resp.status_code < 300):
        raise ValueError(f"calendar_create_failed:{resp.status_code} — {resp.text[:200]}")

    api_data = resp.json()
    receipt = _build_receipt(
        event_payload=event_payload,
        api_response=api_data,
        outbox_path=active.skill_blanca_connector_outbox_path,
    )
    return receipt


# ── Helpers ───────────────────────────────────────────────────────────────────


def _parse_dt(value: str) -> datetime:
    value = value.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f"calendar_invalid_datetime: '{value}' — usar ISO 8601")


def _check_writes_enabled(settings: AppSettings) -> None:
    if not settings.skill_blanca_connector_writes_enabled:
        raise ValueError(
            "calendar_create_disabled: Las escrituras del conector están deshabilitadas. "
            "Activa LOOMBIT_OPERATOR_SKILL_BLANCA_CONNECTOR_WRITES_ENABLED=true en .env"
        )


def _build_receipt(
    *,
    event_payload: dict[str, Any],
    api_response: dict[str, Any],
    outbox_path: Path,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    event_id = str(api_response.get("id", ""))
    html_link = str(api_response.get("htmlLink", ""))
    summary = str(event_payload.get("summary", ""))

    receipt: dict[str, Any] = {
        "operation_type": "calendar_create",
        "status": "created",
        "created_at": now.isoformat(),
        "summary": summary,
        "event_id": event_id,
        "html_link": html_link,
        "provider": "google_calendar_api",
        "event_payload": event_payload,
        "api_response": api_response,
        "dod": "🟢",
    }

    # Guardar recibo JSON
    safe_summary = re.sub(r"[^\w.-]", "_", summary)[:40]
    base_name = f"{now.strftime('%Y%m%dT%H%M%SZ')}_calendar_{safe_summary}"
    outbox_path.mkdir(parents=True, exist_ok=True)

    json_path = outbox_path / f"{base_name}.json"
    json_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")
    receipt["receipt_path"] = str(json_path)

    # Guardar .ics (iCalendar) para compatibilidad universal
    ics_path = outbox_path / f"{base_name}.ics"
    ics_path.write_text(_build_ics(event_payload, event_id, summary), encoding="utf-8")
    receipt["ics_path"] = str(ics_path)

    return receipt


def _build_ics(event_payload: dict[str, Any], event_id: str, summary: str) -> str:
    now_str = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    start = event_payload.get("start", {})
    end = event_payload.get("end", {})

    if "date" in start:
        dtstart = f"DTSTART;VALUE=DATE:{start['date'].replace('-', '')}"
        dtend = f"DTEND;VALUE=DATE:{end['date'].replace('-', '')}"
    else:
        raw_start = str(start.get("dateTime", "")).replace(":", "").replace("-", "")
        raw_end = str(end.get("dateTime", "")).replace(":", "").replace("-", "")
        tz = str(start.get("timeZone", "Europe/Madrid"))
        dtstart = f"DTSTART;TZID={tz}:{raw_start[:15]}"
        dtend = f"DTEND;TZID={tz}:{raw_end[:15]}"

    description = str(event_payload.get("description", "")).replace("\n", "\\n")
    location = str(event_payload.get("location", ""))

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Loombit Operator//Skill Blanca//ES",
        "BEGIN:VEVENT",
        f"UID:{event_id}@loombit",
        f"DTSTAMP:{now_str}",
        dtstart,
        dtend,
        f"SUMMARY:{summary}",
    ]
    if description:
        lines.append(f"DESCRIPTION:{description}")
    if location:
        lines.append(f"LOCATION:{location}")
    attendees = event_payload.get("attendees", [])
    for att in attendees:
        email = att.get("email", "")
        if email:
            lines.append(f"ATTENDEE;RSVP=TRUE:mailto:{email}")
    lines += ["END:VEVENT", "END:VCALENDAR", ""]
    return "\r\n".join(lines)


def snapshot_calendar_outbox(settings: AppSettings | None = None) -> dict[str, Any]:
    """Lista los recibos de eventos creados."""
    active = settings or get_settings()
    outbox = active.skill_blanca_connector_outbox_path
    if not outbox.exists():
        return {"outbox_path": str(outbox), "count": 0, "receipts": []}
    files = sorted(outbox.glob("*_calendar_*.json"), reverse=True)
    items = []
    for f in files[:20]:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            items.append(
                {
                    "file": f.name,
                    "created_at": data.get("created_at", ""),
                    "summary": data.get("summary", ""),
                    "event_id": data.get("event_id", ""),
                    "html_link": data.get("html_link", ""),
                    "status": data.get("status", ""),
                }
            )
        except (json.JSONDecodeError, OSError):
            pass
    return {"outbox_path": str(outbox), "count": len(files), "receipts": items}
