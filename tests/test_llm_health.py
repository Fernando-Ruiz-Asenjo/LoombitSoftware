"""Chequeo de contexto del LLM (llm_health.check_context): hace RUIDOSO el fallo silencioso de que el
modelo se cargue con menos contexto del que Loombit espera (→ 400 'n_keep >= n_ctx' en vivo, gate verde).
"""

from __future__ import annotations

from types import SimpleNamespace

import httpx

from loombit_operator import llm_health


def _settings(ctx=8192, model="qwen2.5-14b-instruct", provider="lm_studio"):
    return SimpleNamespace(
        llm_context_length=ctx,
        llm_model_name=model,
        llm_provider=provider,
        llm_base_url="http://localhost:1234/v1",
    )


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def _patch_models(monkeypatch, modelos):
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _Resp({"data": modelos}))


def test_native_models_url_desde_v1():
    assert (
        llm_health._native_models_url("http://localhost:1234/v1")
        == "http://localhost:1234/api/v0/models"
    )
    assert llm_health._native_models_url("http://h:9/v1/") == "http://h:9/api/v0/models"


def test_contexto_suficiente_ok(monkeypatch):
    _patch_models(
        monkeypatch,
        [{"id": "qwen2.5-14b-instruct", "state": "loaded", "loaded_context_length": 8192}],
    )
    r = llm_health.check_context(_settings(ctx=8192))
    assert r["ok"] is True and r["status"] == "ok"
    assert r["loaded_context_length"] == 8192


def test_contexto_insuficiente_avisa(monkeypatch):
    # EL caso clave: cargado 4096 < configurado 8192 → ruidoso, ok=False, con la orden de recarga.
    _patch_models(
        monkeypatch,
        [{"id": "qwen2.5-14b-instruct", "state": "loaded", "loaded_context_length": 4096}],
    )
    r = llm_health.check_context(_settings(ctx=8192))
    assert r["ok"] is False and r["status"] == "context_too_small"
    assert r["loaded_context_length"] == 4096
    assert "lms load" in r["message"] and "8192" in r["message"]


def test_modelo_no_cargado(monkeypatch):
    _patch_models(
        monkeypatch, [{"id": "otro-modelo", "state": "loaded", "loaded_context_length": 8192}]
    )
    r = llm_health.check_context(_settings())
    assert r["ok"] is False and r["status"] == "not_loaded"


def test_modelo_presente_pero_no_loaded(monkeypatch):
    _patch_models(
        monkeypatch,
        [{"id": "qwen2.5-14b-instruct", "state": "not-loaded", "loaded_context_length": 8192}],
    )
    r = llm_health.check_context(_settings())
    assert r["ok"] is False and r["status"] == "not_loaded"


def test_lm_studio_inalcanzable_no_es_fallo(monkeypatch):
    def _boom(*a, **k):
        raise httpx.ConnectError("conn refused")

    monkeypatch.setattr(httpx, "get", _boom)
    r = llm_health.check_context(_settings())
    assert r["ok"] is True and r["status"] == "unreachable"  # apagado ≠ bug de contexto


def test_provider_disabled_se_salta():
    r = llm_health.check_context(_settings(provider="disabled"))
    assert r["ok"] is True and r["status"] == "disabled"
