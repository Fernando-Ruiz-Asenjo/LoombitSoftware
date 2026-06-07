"""
Router — Skill Blanca OAuth (Google / Microsoft).

Endpoints:
  GET  /skill-blanca/oauth/{provider}/start        → authorization_url para abrir en el navegador
  GET  /skill-blanca/oauth/{provider}/callback     → intercambia code por token (Google redirige aquí)
  GET  /skill-blanca/oauth/{provider}/status       → snapshot redactado del token store
  DELETE /skill-blanca/oauth/{provider}/disconnect → borra el token local

Flujo normal Google:
  1. Abrir /skill-blanca/oauth/google/start → copiar authorization_url → pegar en navegador
  2. Google redirige a http://127.0.0.1:8787/skill-blanca/oauth/google/callback?code=...&state=...
  3. El callback intercambia el code → guarda token en runtime/local/
  4. /status confirma access_token_present: true

🟡 Estado: contrato implementado. Pendiente piloto real (Fase 1).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse

from ..config import get_settings
from ..skill_blanca_oauth import (
    OAuthTokenStore,
    build_authorization_url,
    complete_callback,
    disconnect,
    oauth_configs_from_settings,
    oauth_readiness,
)

router = APIRouter(prefix="/skill-blanca/oauth", tags=["skill-blanca-oauth"])

_SUPPORTED = {"google", "microsoft"}


def _get_config(provider: str):
    if provider not in _SUPPORTED:
        raise HTTPException(status_code=404, detail=f"Provider '{provider}' not supported. Use: {sorted(_SUPPORTED)}")
    settings = get_settings()
    configs = oauth_configs_from_settings(settings)
    return configs[provider], settings


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/{provider}/start")
def oauth_start(provider: str):
    """
    Genera la URL de autorización. Ábrela en el navegador para conectar la cuenta.
    Si el provider no está habilitado en .env devuelve 403.
    """
    config, _ = _get_config(provider)
    if not config.enabled:
        raise HTTPException(
            status_code=403,
            detail=f"OAuth para '{provider}' está deshabilitado. "
                   f"Actívalo en .env: LOOMBIT_OPERATOR_SKILL_BLANCA_{provider.upper()}_OAUTH_ENABLED=true",
        )
    if not config.configured:
        raise HTTPException(
            status_code=422,
            detail=f"OAuth para '{provider}' no está configurado. "
                   f"Faltan: client_id, client_secret y/o redirect_uri en .env",
        )
    try:
        result = build_authorization_url(config)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


@router.get("/{provider}/callback")
def oauth_callback(
    provider: str,
    code: str = Query(..., description="Authorization code de Google/Microsoft"),
    state: str = Query(..., description="State token generado por /start"),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
):
    """
    Punto de llegada del redirect de Google/Microsoft.
    Intercambia el code por access_token + refresh_token y los guarda localmente.
    """
    config, _ = _get_config(provider)
    if error:
        raise HTTPException(
            status_code=400,
            detail=f"OAuth error de '{provider}': {error} — {error_description or ''}",
        )
    try:
        result = complete_callback(config, code=code, state=state)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Token exchange failed: {exc}") from exc

    # HTML de confirmación para cuando Google redirige el navegador aquí
    html = f"""
    <html><head><title>Loombit OAuth</title></head>
    <body style="font-family:sans-serif;max-width:480px;margin:60px auto;text-align:center">
      <h2>✅ {provider.capitalize()} conectado</h2>
      <p>Token guardado localmente. Puedes cerrar esta pestaña.</p>
      <pre style="text-align:left;background:#f4f4f4;padding:12px;border-radius:6px;font-size:12px">{_format_token(result)}</pre>
    </body></html>
    """
    return HTMLResponse(content=html, status_code=200)


@router.get("/{provider}/status")
def oauth_status(provider: str):
    """
    Snapshot redactado del estado OAuth del provider.
    Nunca expone tokens — solo indica si están presentes.
    """
    _get_config(provider)  # valida provider
    settings = get_settings()
    return oauth_readiness(settings)["providers"][provider]


@router.get("/status")
def oauth_status_all():
    """Snapshot redactado de todos los providers."""
    settings = get_settings()
    return oauth_readiness(settings)


@router.delete("/{provider}/disconnect")
def oauth_disconnect(provider: str):
    """
    Borra el token local del provider. Reversible: puedes volver a conectar
    con /start sin tocar .env.
    """
    _get_config(provider)  # valida provider
    settings = get_settings()
    return disconnect(settings.skill_blanca_oauth_token_store_path, provider)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _format_token(result: dict) -> str:
    token = result.get("token", {})
    lines = [
        f"provider:              {token.get('provider', '')}",
        f"access_token_present:  {token.get('access_token_present', False)}",
        f"refresh_token_present: {token.get('refresh_token_present', False)}",
        f"expires_at:            {token.get('expires_at', 'n/a')}",
        f"scope:                 {token.get('scope', '')}",
    ]
    return "\n".join(lines)
