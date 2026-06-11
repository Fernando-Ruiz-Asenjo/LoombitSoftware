"""
onboarding.py — el dueño, sin fricción (la primera palabra del producto: "Hola, Fernando").

Un usuario nuevo arranca con la identidad vacía (BLANCO). Aquí se decide si falta onboarding y se
DERIVA el nombre de Google al conectar (zero-friction), sin pisar jamás un nombre que el usuario ya
puso a mano (su verdad manda). Núcleo blanco: ningún dato de usuario hardcodeado.
"""

from __future__ import annotations

from typing import Any


def estado_onboarding(memory: Any) -> dict[str, Any]:
    """¿Necesita el usuario poner su nombre? (para que la UI lo pida una sola vez)."""
    name = (memory.owner.get("name") or "").strip()
    return {"needs_onboarding": not name, "name": name}


def derivar_owner_de_google(memory: Any, perfil: dict[str, Any]) -> dict[str, str]:
    """Si el dueño AÚN no tiene nombre y Google ofrece uno, lo adopta (con su email). No sobrescribe
    un nombre ya puesto por el usuario. Si Google no da nombre, no inventa nada. Devuelve el owner.
    """
    if (memory.owner.get("name") or "").strip():
        return dict(memory.owner)  # la verdad del usuario manda: no se toca
    nombre = (perfil.get("name") or perfil.get("given_name") or "").strip()
    campos: dict[str, str] = {}
    if nombre:
        campos["name"] = nombre
    email = (perfil.get("email") or "").strip()
    if email:
        campos["email"] = email
    if campos:
        return memory.set_owner(**campos)
    return dict(memory.owner)


def intentar_onboarding_google(settings: Any, memory: Any) -> dict[str, Any]:
    """Best-effort: si falta el nombre y Google está conectado, lo trae del perfil (userinfo) y lo
    adopta. Nunca rompe: ante cualquier fallo, deja el estado como estaba. Devuelve el estado."""
    if (memory.owner.get("name") or "").strip():
        return estado_onboarding(memory)
    try:
        import httpx

        from .skill_blanca_oauth import fresh_access_token

        token = fresh_access_token(settings, "google")
        if token:
            with httpx.Client(timeout=8) as c:
                r = c.get(
                    "https://www.googleapis.com/oauth2/v2/userinfo",
                    headers={"Authorization": f"Bearer {token}"},
                )
            if r.status_code == 200:
                derivar_owner_de_google(memory, r.json())
    except Exception:
        pass
    return estado_onboarding(memory)
