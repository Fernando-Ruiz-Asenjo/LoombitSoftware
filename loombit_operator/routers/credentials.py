"""
routers/credentials.py — API local de la bóveda de credenciales (gestor de contraseñas de Loombit).

Solo escucha en 127.0.0.1 (el servidor no se expone a la red). El secreto se guarda cifrado y NUNCA
se devuelve en las respuestas (el listado no lo incluye). Das una credencial una vez; Loombit la usa.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..credentials import CredentialVault

router = APIRouter(prefix="/credentials", tags=["credentials"])


class CredencialIn(BaseModel):
    service: str
    username: str
    secret: str
    notes: str = ""


def _vault() -> CredentialVault:
    return CredentialVault()


@router.get("")
def listar() -> dict:
    """Lista las credenciales guardadas SIN los secretos."""
    return {"credentials": _vault().list()}


@router.post("")
def guardar(body: CredencialIn) -> dict:
    """Guarda/actualiza una credencial (se cifra en reposo). No devuelve el secreto."""
    try:
        _vault().set(body.service, body.username, body.secret, body.notes)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"ok": True, "service": body.service}


@router.delete("/{service}")
def borrar(service: str) -> dict:
    return {"ok": _vault().delete(service)}
