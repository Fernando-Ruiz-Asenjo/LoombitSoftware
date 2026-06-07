"""
Tests 🟡 del router OAuth — contrato de API con mocks.
No hacen llamadas reales a Google/Microsoft.
Para pasar a 🟢 ejecutar con cuenta de prueba real y recibo guardado.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from loombit_operator.main import app
from loombit_operator.config import AppSettings

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def tmp_token_store(tmp_path: Path) -> Path:
    return tmp_path / "oauth_tokens.json"


@pytest.fixture()
def google_settings(tmp_token_store: Path):
    return AppSettings(
        skill_blanca_google_oauth_enabled=True,
        skill_blanca_google_client_id="test-client-id",
        skill_blanca_google_client_secret="test-client-secret",
        skill_blanca_google_redirect_uri="http://127.0.0.1:8787/skill-blanca/oauth/google/callback",
        skill_blanca_google_scopes="https://www.googleapis.com/auth/gmail.send",
        skill_blanca_oauth_token_store_path=tmp_token_store,
        skill_blanca_oauth_local_config_path=tmp_token_store.parent / "oauth_config.json",
    )


@pytest.fixture()
def client(google_settings):
    with patch(
        "loombit_operator.routers.skill_blanca_oauth.get_settings", return_value=google_settings
    ):
        with patch(
            "loombit_operator.skill_blanca_oauth.get_settings", return_value=google_settings
        ):
            yield TestClient(app)


# ── Tests /start ──────────────────────────────────────────────────────────────


def test_start_returns_authorization_url(client):
    with (
        patch("loombit_operator.routers.skill_blanca_oauth.get_settings"),
        patch(
            "loombit_operator.routers.skill_blanca_oauth.oauth_configs_from_settings"
        ) as mock_cfgs,
        patch("loombit_operator.routers.skill_blanca_oauth.build_authorization_url") as mock_build,
    ):

        from loombit_operator.skill_blanca_oauth import OAuthProviderConfig
        from pathlib import Path

        fake_config = OAuthProviderConfig(
            provider="google",
            enabled=True,
            client_id="test-client-id",
            client_secret="test-secret",
            redirect_uri="http://127.0.0.1:8787/skill-blanca/oauth/google/callback",
            scopes=("https://www.googleapis.com/auth/gmail.send",),
            token_store_path=Path("/tmp/tokens.json"),
        )
        mock_cfgs.return_value = {"google": fake_config, "microsoft": fake_config}
        mock_build.return_value = {
            "authorization_type": "skill_blanca_oauth_authorization_url",
            "provider": "google",
            "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?client_id=test&...",
            "state": "SB_OAUTH_ABC123",
            "redirect_uri": "http://127.0.0.1:8787/skill-blanca/oauth/google/callback",
            "scopes": ["https://www.googleapis.com/auth/gmail.send"],
        }

        resp = TestClient(app).get("/skill-blanca/oauth/google/start")
        assert resp.status_code == 200
        data = resp.json()
        assert data["authorization_type"] == "skill_blanca_oauth_authorization_url"
        assert "authorization_url" in data
        assert data["provider"] == "google"


def test_start_returns_403_when_disabled():
    from loombit_operator.skill_blanca_oauth import OAuthProviderConfig
    from pathlib import Path

    disabled_config = OAuthProviderConfig(
        provider="google",
        enabled=False,
        client_id="",
        client_secret="",
        redirect_uri="",
        scopes=(),
        token_store_path=Path("/tmp/tokens.json"),
    )
    with (
        patch("loombit_operator.routers.skill_blanca_oauth.get_settings"),
        patch(
            "loombit_operator.routers.skill_blanca_oauth.oauth_configs_from_settings",
            return_value={"google": disabled_config, "microsoft": disabled_config},
        ),
    ):
        resp = TestClient(app).get("/skill-blanca/oauth/google/start")
        assert resp.status_code == 403


def test_start_returns_404_for_unknown_provider():
    resp = TestClient(app).get("/skill-blanca/oauth/twitter/start")
    assert resp.status_code == 404


# ── Tests /status ─────────────────────────────────────────────────────────────


def test_status_returns_snapshot(tmp_path):
    token_store = tmp_path / "tokens.json"
    from loombit_operator.skill_blanca_oauth import OAuthProviderConfig

    fake_config = OAuthProviderConfig(
        provider="google",
        enabled=False,
        client_id="",
        client_secret="",
        redirect_uri="",
        scopes=(),
        token_store_path=token_store,
    )
    fake_readiness = {
        "providers": {
            "google": {
                "provider": "google",
                "enabled": False,
                "configured": False,
                "connected": False,
                "authorization_url_ready": False,
                "missing": ["google_oauth_enabled", "google_client_id"],
                "redirect_uri": "",
                "scopes": [],
            }
        }
    }
    with (
        patch("loombit_operator.routers.skill_blanca_oauth.get_settings"),
        patch(
            "loombit_operator.routers.skill_blanca_oauth.oauth_configs_from_settings",
            return_value={"google": fake_config, "microsoft": fake_config},
        ),
        patch(
            "loombit_operator.routers.skill_blanca_oauth.oauth_readiness",
            return_value=fake_readiness,
        ),
    ):
        resp = TestClient(app).get("/skill-blanca/oauth/google/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["provider"] == "google"
        assert data["connected"] is False


# ── Tests /disconnect ─────────────────────────────────────────────────────────


def test_disconnect_returns_not_connected_when_no_token(tmp_path):
    token_store = tmp_path / "tokens.json"
    from loombit_operator.skill_blanca_oauth import OAuthProviderConfig

    fake_config = OAuthProviderConfig(
        provider="google",
        enabled=False,
        client_id="",
        client_secret="",
        redirect_uri="",
        scopes=(),
        token_store_path=token_store,
    )
    settings_mock = AppSettings(
        skill_blanca_oauth_token_store_path=token_store,
        skill_blanca_oauth_local_config_path=tmp_path / "cfg.json",
    )
    with (
        patch(
            "loombit_operator.routers.skill_blanca_oauth.get_settings", return_value=settings_mock
        ),
        patch(
            "loombit_operator.routers.skill_blanca_oauth.oauth_configs_from_settings",
            return_value={"google": fake_config, "microsoft": fake_config},
        ),
    ):
        resp = TestClient(app).delete("/skill-blanca/oauth/google/disconnect")
        assert resp.status_code == 200
        data = resp.json()
        assert data["operation_type"] == "skill_blanca_oauth_disconnect"
        assert data["status"] == "not_connected"
