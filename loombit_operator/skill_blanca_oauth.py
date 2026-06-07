"""
Skill A — OAuth local para Google y Microsoft.
Flujo: authorization-url → callback → token store → refresh → disconnect.
🟡 Estado: fake-tested. Pendiente piloto real contra cuenta de prueba (Fase 1).
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from uuid import uuid4

import httpx

from .config import AppSettings
from .config import get_settings  # noqa: F401  (objetivo de patch en tests)

SUPPORTED_PROVIDERS = {"google", "microsoft"}
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
MICROSOFT_AUTH_URL_TEMPLATE = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize"
MICROSOFT_TOKEN_URL_TEMPLATE = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"


@dataclass(frozen=True)
class OAuthProviderConfig:
    provider: str
    enabled: bool
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: tuple[str, ...]
    token_store_path: Path
    tenant: str = "common"

    @property
    def configured(self) -> bool:
        # En el flujo "app de escritorio" + PKCE el client_secret es opcional,
        # así que no se exige aquí. Lo imprescindible es client_id, redirect y scopes.
        return bool(self.client_id and self.redirect_uri and self.scopes)

    @property
    def auth_url(self) -> str:
        if self.provider == "google":
            return GOOGLE_AUTH_URL
        if self.provider == "microsoft":
            return MICROSOFT_AUTH_URL_TEMPLATE.format(tenant=self.tenant or "common")
        raise ValueError(f"unsupported oauth provider: {self.provider}")

    @property
    def token_url(self) -> str:
        if self.provider == "google":
            return GOOGLE_TOKEN_URL
        if self.provider == "microsoft":
            return MICROSOFT_TOKEN_URL_TEMPLATE.format(tenant=self.tenant or "common")
        raise ValueError(f"unsupported oauth provider: {self.provider}")


class OAuthTokenStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def snapshot(self) -> dict[str, Any]:
        raw = self._load()
        providers = {
            p: _redacted(item)
            for p, item in raw.get("providers", {}).items()
            if isinstance(item, dict)
        }
        return {
            "store_type": "skill_blanca_oauth_token_store",
            "path": str(self.path),
            "exists": self.path.exists(),
            "providers": providers,
            "pending_authorizations": _pending_snapshot(raw),
            "safety_contract": {
                "local_only": True,
                "does_not_log_tokens": True,
                "snapshots_are_redacted": True,
            },
        }

    def token_for(self, provider: str) -> dict[str, Any]:
        raw = self._load()
        item = raw.get("providers", {}).get(provider, {})
        return dict(item) if isinstance(item, dict) else {}

    def store_pending(self, provider: str, state: str, code_verifier: str = "") -> None:
        raw = self._load()
        raw.setdefault("pending_authorizations", {})[state] = {
            "provider": provider,
            "created_at": datetime.now(UTC).isoformat(),
            "code_verifier": code_verifier,
        }
        self._save(raw)

    def consume_pending(self, provider: str, state: str) -> dict[str, Any]:
        raw = self._load()
        pending = raw.setdefault("pending_authorizations", {})
        item = pending.pop(state, {})
        if not isinstance(item, dict) or item.get("provider") != provider:
            self._save(raw)
            raise ValueError("oauth_state_not_found")
        self._save(raw)
        return dict(item)

    def store_token(self, provider: str, payload: dict[str, Any]) -> dict[str, Any]:
        raw = self._load()
        now = datetime.now(UTC)
        item = {**payload, "provider": provider, "updated_at": now.isoformat()}
        expires_in = payload.get("expires_in")
        if isinstance(expires_in, (int, float)):
            item["expires_at"] = (now + timedelta(seconds=int(expires_in))).isoformat()
        raw.setdefault("providers", {})[provider] = item
        self._save(raw)
        return _redacted(item)

    def delete_token(self, provider: str) -> dict[str, Any]:
        raw = self._load()
        existed = provider in raw.get("providers", {})
        raw.setdefault("providers", {}).pop(provider, None)
        self._save(raw)
        return {
            "operation_type": "skill_blanca_oauth_disconnect",
            "provider": provider,
            "status": "disconnected" if existed else "not_connected",
        }

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"providers": {}, "pending_authorizations": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"providers": {}, "pending_authorizations": {}}
        if not isinstance(data, dict):
            return {"providers": {}, "pending_authorizations": {}}
        data.setdefault("providers", {})
        data.setdefault("pending_authorizations", {})
        return data

    def _save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ── Funciones públicas ────────────────────────────────────────────────────────


def oauth_configs_from_settings(settings: AppSettings) -> dict[str, OAuthProviderConfig]:
    store_path = settings.skill_blanca_oauth_token_store_path
    base = {
        "google": OAuthProviderConfig(
            provider="google",
            enabled=settings.skill_blanca_google_oauth_enabled,
            client_id=settings.skill_blanca_google_client_id,
            client_secret=settings.skill_blanca_google_client_secret,
            redirect_uri=settings.skill_blanca_google_redirect_uri,
            scopes=_split(settings.skill_blanca_google_scopes),
            token_store_path=store_path,
        ),
        "microsoft": OAuthProviderConfig(
            provider="microsoft",
            enabled=settings.skill_blanca_microsoft_oauth_enabled,
            client_id=settings.skill_blanca_microsoft_client_id,
            client_secret=settings.skill_blanca_microsoft_client_secret,
            redirect_uri=settings.skill_blanca_microsoft_redirect_uri,
            scopes=_split(settings.skill_blanca_microsoft_scopes),
            token_store_path=store_path,
            tenant=settings.skill_blanca_microsoft_tenant,
        ),
    }
    return _apply_local_config(settings, base)


def oauth_readiness(settings: AppSettings) -> dict[str, Any]:
    configs = oauth_configs_from_settings(settings)
    store = OAuthTokenStore(settings.skill_blanca_oauth_token_store_path)
    snap = store.snapshot()
    return {
        "readiness_type": "skill_blanca_oauth_readiness",
        "providers": {p: _provider_readiness(c, snap) for p, c in configs.items()},
        "token_store": snap,
        "safety_contract": {
            "disabled_by_default": True,
            "tokens_stay_local": True,
            "snapshots_are_redacted": True,
        },
    }


def build_authorization_url(config: OAuthProviderConfig, *, state: str = "") -> dict[str, Any]:
    _ensure(config.provider)
    if not config.enabled:
        raise ValueError("oauth_provider_disabled")
    if not config.configured:
        raise ValueError("oauth_provider_not_configured")
    active_state = state or f"SB_OAUTH_{uuid4().hex.upper()}"
    code_verifier, code_challenge = _generate_pkce()
    store = OAuthTokenStore(config.token_store_path)
    store.store_pending(config.provider, active_state, code_verifier=code_verifier)
    params: dict[str, str] = {
        "client_id": config.client_id,
        "redirect_uri": config.redirect_uri,
        "response_type": "code",
        "scope": " ".join(config.scopes),
        "state": active_state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    if config.provider == "google":
        params.update(access_type="offline", prompt="consent", include_granted_scopes="true")
    if config.provider == "microsoft":
        params["response_mode"] = "query"
    return {
        "authorization_type": "skill_blanca_oauth_authorization_url",
        "provider": config.provider,
        "authorization_url": f"{config.auth_url}?{urlencode(params)}",
        "state": active_state,
        "redirect_uri": config.redirect_uri,
        "scopes": list(config.scopes),
    }


def complete_callback(
    config: OAuthProviderConfig,
    *,
    code: str,
    state: str,
    http_post: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    _ensure(config.provider)
    if not config.enabled:
        raise ValueError("oauth_provider_disabled")
    if not config.configured:
        raise ValueError("oauth_provider_not_configured")
    if not code.strip():
        raise ValueError("oauth_code_required")
    store = OAuthTokenStore(config.token_store_path)
    pending = store.consume_pending(config.provider, state)
    code_verifier = str(pending.get("code_verifier", ""))
    payload = {
        "client_id": config.client_id,
        "code": code,
        "redirect_uri": config.redirect_uri,
        "grant_type": "authorization_code",
    }
    # En clientes "app de escritorio" el secret no es confidencial y puede faltar
    # (PKCE protege el intercambio). Solo se envía si está configurado.
    if config.client_secret:
        payload["client_secret"] = config.client_secret
    if code_verifier:
        payload["code_verifier"] = code_verifier
    if config.provider == "microsoft":
        payload["scope"] = " ".join(config.scopes)
    post = http_post or httpx.post
    resp = post(config.token_url, data=payload, timeout=20)
    _check_status(resp, "oauth_token_exchange_failed")
    token = resp.json()
    if not isinstance(token, dict) or not token.get("access_token"):
        raise ValueError("oauth_token_response_missing_access_token")
    redacted = store.store_token(config.provider, token)
    return {
        "completion_type": "skill_blanca_oauth_callback",
        "provider": config.provider,
        "status": "connected",
        "token": redacted,
    }


def refresh_token(
    config: OAuthProviderConfig,
    *,
    http_post: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    _ensure(config.provider)
    if not config.enabled:
        raise ValueError("oauth_provider_disabled")
    if not config.configured:
        raise ValueError("oauth_provider_not_configured")
    store = OAuthTokenStore(config.token_store_path)
    current = store.token_for(config.provider)
    refresh = str(current.get("refresh_token", ""))
    if not refresh:
        raise ValueError("oauth_refresh_token_missing")
    payload = {
        "client_id": config.client_id,
        "refresh_token": refresh,
        "grant_type": "refresh_token",
    }
    if config.client_secret:
        payload["client_secret"] = config.client_secret
    if config.provider == "microsoft":
        payload["scope"] = " ".join(config.scopes)
    post = http_post or httpx.post
    resp = post(config.token_url, data=payload, timeout=20)
    _check_status(resp, "oauth_token_refresh_failed")
    token = resp.json()
    if not isinstance(token, dict) or not token.get("access_token"):
        raise ValueError("oauth_refresh_response_missing_access_token")
    if "refresh_token" not in token:
        token["refresh_token"] = refresh
    redacted = store.store_token(config.provider, token)
    return {
        "refresh_type": "skill_blanca_oauth_refresh",
        "provider": config.provider,
        "status": "refreshed",
        "token": redacted,
    }


def disconnect(token_store_path: Path, provider: str) -> dict[str, Any]:
    _ensure(provider)
    return OAuthTokenStore(token_store_path).delete_token(provider)


def load_access_token(token_store_path: Path, provider: str) -> str:
    _ensure(provider)
    return str(OAuthTokenStore(token_store_path).token_for(provider).get("access_token", ""))


def ensure_fresh_access_token(
    config: OAuthProviderConfig,
    *,
    skew_seconds: int = 60,
    http_post: Callable[..., Any] | None = None,
) -> str:
    """
    Devuelve un access_token válido para el provider, refrescándolo de forma
    transparente si ha expirado (o está a menos de `skew_seconds` de hacerlo).

    El usuario conecta una vez; esta función mantiene viva la sesión usando el
    refresh_token. Lanza ValueError si no hay token o no se puede refrescar.
    """
    _ensure(config.provider)
    store = OAuthTokenStore(config.token_store_path)
    current = store.token_for(config.provider)
    access = str(current.get("access_token", ""))
    if not access:
        raise ValueError("oauth_not_connected")

    if not _token_expired(current, skew_seconds=skew_seconds):
        return access

    if not str(current.get("refresh_token", "")):
        raise ValueError("oauth_refresh_token_missing")

    refresh_token(config, http_post=http_post)
    return str(store.token_for(config.provider).get("access_token", ""))


# ── Helpers privados ──────────────────────────────────────────────────────────


def _generate_pkce() -> tuple[str, str]:
    """Genera (code_verifier, code_challenge) con método S256 (RFC 7636)."""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode("ascii")
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def _token_expired(token: dict[str, Any], *, skew_seconds: int = 60) -> bool:
    """True si el token no tiene expires_at o ya caducó (con margen de seguridad)."""
    expires_at = str(token.get("expires_at", ""))
    if not expires_at:
        return True
    try:
        deadline = datetime.fromisoformat(expires_at)
    except ValueError:
        return True
    return datetime.now(UTC) >= deadline - timedelta(seconds=skew_seconds)


def _ensure(provider: str) -> None:
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(f"unsupported_oauth_provider:{provider}")


def _check_status(resp: Any, error_prefix: str) -> None:
    code = int(getattr(resp, "status_code", 0))
    if not (200 <= code < 300):
        raise ValueError(f"{error_prefix}:{code}")


def _split(value: str) -> tuple[str, ...]:
    return tuple(v for v in value.split() if v.strip())


def _redacted(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "provider": item.get("provider", ""),
        "updated_at": item.get("updated_at", ""),
        "expires_at": item.get("expires_at", ""),
        "scope": item.get("scope", ""),
        "token_type": item.get("token_type", ""),
        "access_token_present": bool(item.get("access_token")),
        "refresh_token_present": bool(item.get("refresh_token")),
    }


def _pending_snapshot(raw: dict[str, Any]) -> dict[str, Any]:
    pending = raw.get("pending_authorizations", {})
    if not isinstance(pending, dict):
        return {"count": 0, "items": []}
    return {
        "count": len(pending),
        "items": [
            {
                "state": s,
                "provider": i.get("provider", "") if isinstance(i, dict) else "",
                "created_at": i.get("created_at", "") if isinstance(i, dict) else "",
            }
            for s, i in pending.items()
        ],
    }


def _provider_readiness(config: OAuthProviderConfig, store_snap: dict[str, Any]) -> dict[str, Any]:
    token = store_snap.get("providers", {}).get(config.provider, {})
    missing = []
    if not config.enabled:
        missing.append(f"{config.provider}_oauth_enabled")
    if not config.client_id:
        missing.append(f"{config.provider}_client_id")
    if not config.client_secret:
        missing.append(f"{config.provider}_client_secret")
    if not config.redirect_uri:
        missing.append(f"{config.provider}_redirect_uri")
    if not config.scopes:
        missing.append(f"{config.provider}_scopes")
    return {
        "provider": config.provider,
        "enabled": config.enabled,
        "configured": config.configured,
        "connected": bool(token.get("access_token_present")),
        "authorization_url_ready": config.enabled and config.configured,
        "missing": missing,
        "redirect_uri": config.redirect_uri,
        "scopes": list(config.scopes),
    }


def _apply_local_config(
    settings: AppSettings, configs: dict[str, OAuthProviderConfig]
) -> dict[str, OAuthProviderConfig]:
    path = settings.skill_blanca_oauth_local_config_path
    if not path.exists():
        return configs
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return configs
    providers = data.get("providers", {})
    if not isinstance(providers, dict):
        return configs
    merged = dict(configs)
    for provider, item in providers.items():
        if provider not in merged or not isinstance(item, dict):
            continue
        base = merged[provider]
        scopes_str = str(item.get("scopes", "")).strip()
        merged[provider] = OAuthProviderConfig(
            provider=provider,
            enabled=bool(item.get("enabled", base.enabled)),
            client_id=str(item.get("client_id", "")).strip() or base.client_id,
            client_secret=str(item.get("client_secret", "")).strip() or base.client_secret,
            redirect_uri=str(item.get("redirect_uri", "")).strip() or base.redirect_uri,
            scopes=_split(scopes_str) or base.scopes,
            token_store_path=base.token_store_path,
            tenant=str(item.get("tenant", "")).strip() or base.tenant,
        )
    return merged
