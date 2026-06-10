"""Defensa local-first: solo Host/Origin locales (anti DNS-rebinding + CSRF)."""

from fastapi.testclient import TestClient

from loombit_operator.main import app
from loombit_operator.seguridad_web import host_permitido, origen_permitido


def test_host_permitido_solo_local():
    assert host_permitido("127.0.0.1:8787") is True
    assert host_permitido("localhost:8787") is True
    assert host_permitido("[::1]:8787") is True
    assert host_permitido("testserver") is True
    assert host_permitido("evil.com:8787") is False
    assert host_permitido("loombit.attacker.io") is False


def test_origen_permitido():
    assert origen_permitido(None) is True  # sin Origin (curl/same-origin) → OK
    assert origen_permitido("http://127.0.0.1:8787") is True
    assert origen_permitido("http://localhost:8787") is True
    assert origen_permitido("https://evil.com") is False
    assert origen_permitido("null") is False


def test_endpoint_rechaza_host_no_local():
    c = TestClient(app)
    r = c.get("/health", headers={"host": "evil.com"})
    assert r.status_code == 403


def test_endpoint_rechaza_origin_externo():
    c = TestClient(app)
    r = c.get("/health", headers={"origin": "https://evil.com"})
    assert r.status_code == 403


def test_endpoint_acepta_local():
    c = TestClient(app)  # Host por defecto = 'testserver' (local), sin Origin
    r = c.get("/health", headers={"origin": "http://127.0.0.1:8787"})
    assert r.status_code == 200
