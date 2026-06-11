"""Arnés de gmail_search — manejo de respuestas de la Gmail API.

BUG real (Fernando 2026-06-10): una búsqueda SIN resultados hacía que Gmail devolviera 204 (cuerpo
vacío, por el filtro `fields`), y el código lo trataba como ERROR ("Gmail API 204") → el agente veía
un fallo y se iba a otra tool (buscar-correo → resumen_financiero). Cero resultados NO es un error.
"""

from __future__ import annotations

import json

import httpx

import loombit_operator.skill_blanca_oauth as oauth
from loombit_operator.tools import connectors


class _FakeResp:
    def __init__(self, status_code: int, text: str = "", data: dict | None = None):
        self.status_code = status_code
        self.text = text
        self._data = data or {}

    def json(self):
        return self._data


class _FakeClient:
    """Sustituye a httpx.Client: la 1ª GET (list) devuelve lo que se le pasa en la fábrica."""

    _resp = _FakeResp(204, "")

    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get(self, url, **k):
        return type(self)._resp


def _patch(monkeypatch, resp: _FakeResp):
    monkeypatch.setattr(oauth, "fresh_access_token", lambda *a, **k: "tok-fake")
    _FakeClient._resp = resp
    monkeypatch.setattr(httpx, "Client", _FakeClient)


def test_gmail_search_204_es_cero_resultados_no_error(monkeypatch):
    _patch(monkeypatch, _FakeResp(204, ""))
    out = json.loads(connectors._gmail_search("zzz-no-existe"))
    assert out["ok"] is True  # NO es un error
    assert out["count"] == 0
    assert out["messages"] == []


def test_gmail_search_error_real_sigue_siendo_error(monkeypatch):
    _patch(monkeypatch, _FakeResp(500, "boom"))  # un fallo de verdad SÍ se reporta
    out = json.loads(connectors._gmail_search("lo que sea"))
    assert out["ok"] is False
    assert "500" in out["error"]
