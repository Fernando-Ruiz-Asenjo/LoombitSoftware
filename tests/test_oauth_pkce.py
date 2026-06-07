"""
Tests del flujo OAuth "app de escritorio": PKCE (S256) y auto-refresh.

Sin red: el POST al token endpoint se inyecta con http_post.
"""

import base64
import hashlib
from urllib.parse import parse_qs, urlparse

import pytest

from loombit_operator.skill_blanca_oauth import (
    OAuthProviderConfig,
    OAuthTokenStore,
    build_authorization_url,
    complete_callback,
    ensure_fresh_access_token,
)


def _google_config(tmp_path, client_secret="secret"):
    return OAuthProviderConfig(
        provider="google",
        enabled=True,
        client_id="cid.apps.googleusercontent.com",
        client_secret=client_secret,
        redirect_uri="http://127.0.0.1:8787/skill-blanca/oauth/google/callback",
        scopes=("https://www.googleapis.com/auth/gmail.send",),
        token_store_path=tmp_path / "tokens.json",
    )


class _FakeResp:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


# ── PKCE ────────────────────────────────────────────────────────────────────


def test_authorization_url_includes_pkce_matching_verifier(tmp_path):
    cfg = _google_config(tmp_path)
    result = build_authorization_url(cfg)

    qs = parse_qs(urlparse(result["authorization_url"]).query)
    assert qs["code_challenge_method"] == ["S256"]
    challenge = qs["code_challenge"][0]

    pending = OAuthTokenStore(cfg.token_store_path).consume_pending("google", result["state"])
    verifier = pending["code_verifier"]
    expected = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    )
    assert challenge == expected


def test_complete_callback_sends_verifier_and_omits_empty_secret(tmp_path):
    cfg = _google_config(tmp_path, client_secret="")  # cliente de escritorio sin secret
    state = build_authorization_url(cfg)["state"]
    captured = {}

    def fake_post(url, data=None, timeout=None):
        captured["data"] = data
        return _FakeResp(200, {"access_token": "AT", "refresh_token": "RT", "expires_in": 3600})

    complete_callback(cfg, code="auth-code", state=state, http_post=fake_post)

    assert captured["data"]["grant_type"] == "authorization_code"
    assert captured["data"]["code_verifier"]
    assert "client_secret" not in captured["data"]


def test_complete_callback_includes_secret_when_present(tmp_path):
    cfg = _google_config(tmp_path, client_secret="shh")
    state = build_authorization_url(cfg)["state"]
    captured = {}

    def fake_post(url, data=None, timeout=None):
        captured["data"] = data
        return _FakeResp(200, {"access_token": "AT", "expires_in": 3600})

    complete_callback(cfg, code="auth-code", state=state, http_post=fake_post)

    assert captured["data"]["client_secret"] == "shh"


# ── Auto-refresh ────────────────────────────────────────────────────────────


def test_ensure_fresh_returns_valid_without_refreshing(tmp_path):
    cfg = _google_config(tmp_path)
    store = OAuthTokenStore(cfg.token_store_path)
    store.store_token("google", {"access_token": "AT", "refresh_token": "RT", "expires_in": 3600})

    def fail_post(*args, **kwargs):
        raise AssertionError("no debería refrescar un token válido")

    assert ensure_fresh_access_token(cfg, http_post=fail_post) == "AT"


def test_ensure_fresh_refreshes_when_expired(tmp_path):
    cfg = _google_config(tmp_path)
    store = OAuthTokenStore(cfg.token_store_path)
    store.store_token("google", {"access_token": "OLD", "refresh_token": "RT", "expires_in": -10})

    def fake_post(url, data=None, timeout=None):
        assert data["grant_type"] == "refresh_token"
        return _FakeResp(200, {"access_token": "NEW", "expires_in": 3600})

    assert ensure_fresh_access_token(cfg, http_post=fake_post) == "NEW"


def test_ensure_fresh_raises_when_not_connected(tmp_path):
    cfg = _google_config(tmp_path)
    with pytest.raises(ValueError, match="oauth_not_connected"):
        ensure_fresh_access_token(cfg)
