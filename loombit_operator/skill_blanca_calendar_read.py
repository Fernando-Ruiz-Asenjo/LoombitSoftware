"""
Skill Blanca — Google Calendar (LECTURA).

El conector de calendario (`skill_blanca_calendar.py`) solo escribía (crear evento).
Aquí va la LECTURA de la agenda: qué tienes hoy. Es percepción read-only (no escribe,
no requiere aprobación) y alimenta el "resumen del día".

Usa `fresh_access_token` (auto-refresh) como el resto de lecturas (gmail_search,
vigilar respuestas). Sin token → error claro; el llamador degrada con elegancia.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from .config import AppSettings, get_settings
from .skill_blanca_oauth import fresh_access_token

CALENDAR_LIST_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
MADRID = ZoneInfo("Europe/Madrid")


def _dia_bounds(now: datetime) -> tuple[str, str]:
    """Inicio y fin del día local (Europe/Madrid) en RFC3339, para timeMin/timeMax."""
    local = now.astimezone(MADRID)
    inicio = datetime.combine(local.date(), time.min, tzinfo=MADRID)
    fin = inicio + timedelta(days=1)
    return inicio.isoformat(), fin.isoformat()


def _parse_events(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convierte la respuesta de la API en una lista simple y ordenada. Pura → testeable."""
    out: list[dict[str, Any]] = []
    for ev in items or []:
        start = ev.get("start", {})
        end = ev.get("end", {})
        all_day = "date" in start
        out.append(
            {
                "summary": ev.get("summary", "(sin título)"),
                "start": start.get("dateTime") or start.get("date", ""),
                "end": end.get("dateTime") or end.get("date", ""),
                "all_day": all_day,
                "location": ev.get("location", ""),
            }
        )
    out.sort(key=lambda e: (not e["all_day"], e["start"]))
    return out


def _listar_eventos(
    active: AppSettings, time_min: str, time_max: str, http_get: Any = None
) -> list[dict[str, Any]]:
    """GET de eventos del calendario primario en [time_min, time_max). Núcleo compartido."""
    try:
        token = fresh_access_token(active, "google")
    except Exception:
        token = None  # sin conexión / sin token → se normaliza abajo
    if not token:
        raise ValueError("calendar_read_no_token")

    get = http_get or httpx.get
    resp = get(
        CALENDAR_LIST_URL,
        headers={"Authorization": f"Bearer {token}"},
        params={
            "timeMin": time_min,
            "timeMax": time_max,
            "singleEvents": "true",
            "orderBy": "startTime",
            "maxResults": 25,
        },
        timeout=15,
    )
    if resp.status_code == 401:
        raise ValueError("calendar_read_unauthorized")
    if not (200 <= resp.status_code < 300):
        raise ValueError(f"calendar_read_failed:{resp.status_code}")
    return _parse_events(resp.json().get("items", []))


def eventos_de_hoy(
    settings: AppSettings | None = None,
    now: datetime | None = None,
    http_get: Any = None,
) -> list[dict[str, Any]]:
    """Devuelve los eventos del calendario primario para HOY (Europe/Madrid).

    Lanza ValueError('calendar_read_no_token') si Google no está conectado."""
    active = settings or get_settings()
    ahora = now or datetime.now(MADRID)
    time_min, time_max = _dia_bounds(ahora)
    return _listar_eventos(active, time_min, time_max, http_get)


def eventos_proximos(
    settings: AppSettings | None = None,
    now: datetime | None = None,
    dias: int = 7,
    incluir_hoy: bool = False,
    http_get: Any = None,
) -> list[dict[str, Any]]:
    """Eventos del calendario en los PRÓXIMOS `dias` (por defecto desde mañana). El brief y el telar
    solo miraban HOY → una reunión cerrada para el jueves no aparecía. Esto cierra ese hueco con la
    fuente autoritativa (el calendario). Lanza ValueError('calendar_read_no_token') si no hay token.
    """
    active = settings or get_settings()
    ahora = (now or datetime.now(MADRID)).astimezone(MADRID)
    desde = ahora.date() if incluir_hoy else ahora.date() + timedelta(days=1)
    time_min = datetime.combine(desde, time.min, tzinfo=MADRID).isoformat()
    time_max = datetime.combine(
        ahora.date() + timedelta(days=dias + 1), time.min, tzinfo=MADRID
    ).isoformat()
    return _listar_eventos(active, time_min, time_max, http_get)
