"""
Defensa LOCAL-FIRST del servidor (Skill C · blanco): solo acepta peticiones cuyo Host y Origin sean
LOCALES. El servidor vive en 127.0.0.1; una web que el usuario visite NO debe poder pilotar su
Loombit. Bloquea dos ataques reales desde el navegador:

  - DNS-rebinding: un dominio atacante que resuelve a 127.0.0.1 → la petición llega con su Host →
    se rechaza (Host no local).
  - CSRF cross-origin: una web hace POST a /agent/run → el navegador manda Origin: https://evil… →
    se rechaza (Origin no local). Las peticiones SIN Origin (curl, server-to-server, same-origin GET)
    se permiten.

Puro y testeable; el middleware es una fina capa sobre las dos funciones.
"""

from __future__ import annotations

from urllib.parse import urlparse

from fastapi import Request
from fastapi.responses import JSONResponse

# Hosts locales aceptables (sin puerto). 'testserver' = cliente de pruebas de Starlette/FastAPI.
_HOSTS_LOCALES = ("127.0.0.1", "localhost", "::1", "testserver")


def _host_base(valor: str) -> str:
    """Host sin puerto ni corchetes IPv6, en minúsculas. '127.0.0.1:8787' → '127.0.0.1'."""
    v = (valor or "").strip().lower()
    if v.startswith("["):  # IPv6 entre corchetes: [::1]:8787
        return v[1:].split("]")[0]
    return v.split(":")[0]


def host_permitido(host: str) -> bool:
    """True si la cabecera Host apunta a un host local (defensa anti DNS-rebinding)."""
    return _host_base(host) in _HOSTS_LOCALES


def origen_permitido(origin: str | None) -> bool:
    """Origin ausente = no es cross-origin de navegador (curl/same-origin) → OK. Si está, debe ser
    local (defensa anti CSRF). Un Origin raro ('null', dominio externo) se rechaza."""
    if not origin:
        return True
    return _host_base(urlparse(origin).hostname or "") in _HOSTS_LOCALES


async def solo_local_middleware(request: Request, call_next):
    """Middleware ASGI: corta antes de tocar ningún router si el Host/Origin no es local."""
    if not host_permitido(request.headers.get("host", "")):
        return JSONResponse({"detail": "Host no permitido (local-first)."}, status_code=403)
    if not origen_permitido(request.headers.get("origin")):
        return JSONResponse({"detail": "Origen no permitido (posible CSRF)."}, status_code=403)
    return await call_next(request)
