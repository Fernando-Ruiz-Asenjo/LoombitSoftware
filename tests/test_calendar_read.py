"""Lectura de la agenda de hoy (Google Calendar, read-only)."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from loombit_operator import skill_blanca_calendar_read as cr


def test_parse_events_sorts_allday_first_and_extracts_fields() -> None:
    items = [
        {
            "summary": "Reunión",
            "start": {"dateTime": "2026-06-08T10:00:00+02:00"},
            "end": {"dateTime": "2026-06-08T11:00:00+02:00"},
        },
        {"summary": "Festivo", "start": {"date": "2026-06-08"}, "end": {"date": "2026-06-09"}},
    ]
    out = cr._parse_events(items)
    assert out[0]["all_day"] is True  # los de todo el día, primero
    assert out[1]["summary"] == "Reunión"
    assert out[1]["start"].startswith("2026-06-08T10")


def test_dia_bounds_cubre_el_dia_local_completo() -> None:
    now = datetime(2026, 6, 8, 15, 0, tzinfo=ZoneInfo("Europe/Madrid"))
    tmin, tmax = cr._dia_bounds(now)
    assert tmin.startswith("2026-06-08T00:00")
    assert tmax.startswith("2026-06-09T00:00")


def test_eventos_de_hoy_sin_token_lanza(monkeypatch) -> None:
    monkeypatch.setattr(cr, "fresh_access_token", lambda s, p: None)
    with pytest.raises(ValueError, match="no_token"):
        cr.eventos_de_hoy(settings=object())


def test_eventos_de_hoy_llama_api_y_parsea(monkeypatch) -> None:
    monkeypatch.setattr(cr, "fresh_access_token", lambda s, p: "tok")
    captured: dict = {}

    class _Resp:
        status_code = 200

        def json(self):
            return {
                "items": [
                    {
                        "summary": "Dentista",
                        "start": {"dateTime": "2026-06-08T17:00:00+02:00"},
                        "end": {"dateTime": "2026-06-08T17:30:00+02:00"},
                    }
                ]
            }

    def fake_get(url, headers=None, params=None, timeout=None):
        captured["params"] = params
        captured["auth"] = headers
        return _Resp()

    out = cr.eventos_de_hoy(settings=object(), http_get=fake_get)
    assert out[0]["summary"] == "Dentista"
    assert captured["params"]["singleEvents"] == "true"
    assert captured["auth"]["Authorization"] == "Bearer tok"


def test_eventos_de_hoy_token_caducado(monkeypatch) -> None:
    monkeypatch.setattr(cr, "fresh_access_token", lambda s, p: "tok")

    class _Resp:
        status_code = 401

    with pytest.raises(ValueError, match="unauthorized"):
        cr.eventos_de_hoy(settings=object(), http_get=lambda *a, **k: _Resp())
