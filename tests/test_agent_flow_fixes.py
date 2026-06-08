"""
Bugs del flujo del agente destapados por un run real de 'crear evento':
  1. calendar _parse_dt no aceptaba ISO con 'Z'/offset → calendar_create fallaba →
     al aprobar, re-pausaba ("aunque lo apruebe sigue saliendo la ventanita").
  2. gmail_search usaba el cliente httpx fuera del `with` → "client has been closed".
  3. daily_brief/calendar_today reventaban con TypeError si el modelo pasaba args.
"""

from __future__ import annotations

import pytest

from loombit_operator import skill_blanca_calendar as cal
from loombit_operator.tools import brief


# ── 1. _parse_dt acepta zona horaria ───────────────────────────────────────────
@pytest.mark.parametrize(
    "value",
    [
        "2026-06-15T09:00:00+02:00",  # offset (lo que emitió el modelo)
        "2026-06-15T07:00:00Z",  # UTC con Z
        "2026-06-15T09:00:00",  # naive
        "2026-06-15T09:00",  # sin segundos
        "2026-06-15",  # solo fecha
    ],
)
def test_parse_dt_acepta_iso_con_zona(value: str) -> None:
    assert cal._parse_dt(value).year == 2026  # ya no lanza calendar_invalid_datetime


def test_parse_dt_rechaza_basura() -> None:
    with pytest.raises(ValueError, match="calendar_invalid_datetime"):
        cal._parse_dt("el jueves a las 9")


def test_compose_event_con_offset_produce_payload_valido() -> None:
    # El caso exacto del bug: antes reventaba aquí.
    payload = cal.compose_event(summary="Reunión con David", start_iso="2026-06-15T09:00:00+02:00")
    assert payload["summary"] == "Reunión con David"
    assert "dateTime" in payload["start"] and "dateTime" in payload["end"]


# ── 2. gmail_search: el cliente se usa dentro del `with` ────────────────────────
def test_gmail_search_no_cierra_el_cliente_antes_del_bucle(monkeypatch) -> None:
    from loombit_operator import skill_blanca_oauth

    monkeypatch.setattr(skill_blanca_oauth, "fresh_access_token", lambda s, p: "tok")

    class _Resp:
        def __init__(self, data):
            self._data = data
            self.status_code = 200
            self.text = ""

        def json(self):
            return self._data

    class _FakeClient:
        closed = False

        def __init__(self, **_):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_):
            _FakeClient.closed = True
            return False

        def get(self, url, **_):
            if _FakeClient.closed:  # el bug: usar el cliente tras cerrarlo
                raise RuntimeError("Cannot send a request, as the client has been closed.")
            if url.rstrip("/").endswith("/messages"):
                return _Resp({"messages": [{"id": "m1"}]})
            return _Resp(
                {"snippet": "hola", "payload": {"headers": [{"name": "Subject", "value": "Hi"}]}}
            )

    import httpx

    monkeypatch.setattr(httpx, "Client", _FakeClient)

    import json

    from loombit_operator.tools.connectors import _gmail_search

    out = json.loads(_gmail_search("david"))
    assert out["ok"] is True
    assert out["count"] == 1
    assert out["messages"][0]["subject"] == "Hi"


# ── 3. tools del día toleran argumentos de más ──────────────────────────────────
def test_daily_brief_tolera_args_extra(monkeypatch) -> None:
    monkeypatch.setattr(brief, "_señales_del_dia", lambda now=None: ["sin eventos hoy"])
    from loombit_operator.llm import LLMClient
    from types import SimpleNamespace

    monkeypatch.setattr(
        LLMClient, "chat", lambda self, m, max_tokens=None: SimpleNamespace(content="ok")
    )
    # El modelo a veces pasa un argumento aunque la tool no tenga ninguno: no debe reventar.
    assert brief._daily_brief(fecha="hoy") == "ok"


def test_calendar_today_tolera_args_extra(monkeypatch) -> None:
    import loombit_operator.skill_blanca_calendar_read as cr

    monkeypatch.setattr(cr, "eventos_de_hoy", lambda *a, **k: [])
    assert "No tienes eventos" in brief._calendar_today(dia="hoy")
