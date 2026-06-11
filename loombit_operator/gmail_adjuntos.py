"""
gmail_adjuntos.py — lector de adjuntos PDF de Gmail para el intake real de facturas (Fase 3).

Núcleo de parseo DETERMINISTA y testeable (detectar partes PDF + decodificar el base64url de Gmail)
separado de la descarga en vivo (que necesita token real). Read-only: solo lee adjuntos, no envía
ni borra nada; los datos no salen de la máquina. La factura extraída entra luego por
`skill_d_fiscal.intake.registrar_factura_desde_texto`.
"""

from __future__ import annotations

import base64
from typing import Any

_GMAIL = "https://gmail.googleapis.com/gmail/v1/users/me"


def _es_pdf(parte: dict[str, Any]) -> bool:
    mime = (parte.get("mimeType") or "").lower()
    nombre = (parte.get("filename") or "").lower()
    return mime == "application/pdf" or nombre.endswith(".pdf")


def partes_pdf(payload: dict[str, Any]) -> list[dict[str, str]]:
    """Recorre el árbol de partes de un mensaje (multipart anidado incluido) y devuelve las partes
    PDF como [{filename, attachment_id}], en orden de aparición. Determinista."""
    salida: list[dict[str, str]] = []

    def _rec(parte: dict[str, Any]) -> None:
        for sub in parte.get("parts", []) or []:
            _rec(sub)
        att = (parte.get("body", {}) or {}).get("attachmentId")
        if att and _es_pdf(parte):
            salida.append(
                {"filename": parte.get("filename", "") or "adjunto.pdf", "attachment_id": att}
            )

    _rec(payload)
    return salida


def decodificar_adjunto(data: str) -> bytes:
    """Decodifica el cuerpo de un adjunto de Gmail (base64 URL-safe, con padding tolerante)."""
    s = (data or "").encode("ascii")
    s += b"=" * (-len(s) % 4)  # Gmail a veces omite el padding
    return base64.urlsafe_b64decode(s)


def descargar_adjunto(
    token: str, message_id: str, attachment_id: str, *, timeout: float = 15.0
) -> bytes:
    """Descarga un adjunto concreto (en vivo, necesita token). Read-only."""
    import httpx

    with httpx.Client(timeout=timeout) as c:
        r = c.get(
            f"{_GMAIL}/messages/{message_id}/attachments/{attachment_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        r.raise_for_status()
        return decodificar_adjunto(r.json().get("data", ""))


def facturas_pdf_de_correo(token: str, message_id: str) -> list[tuple[str, bytes]]:
    """Devuelve los PDF adjuntos de un correo como [(filename, bytes)] (en vivo, necesita token).
    Best-effort: si algo falla, devuelve lo que pudo. Read-only — no toca el correo."""
    import httpx

    out: list[tuple[str, bytes]] = []
    try:
        with httpx.Client(timeout=15.0) as c:
            r = c.get(
                f"{_GMAIL}/messages/{message_id}",
                headers={"Authorization": f"Bearer {token}"},
                params={"format": "full"},
            )
            if r.status_code != 200:
                return out
            for parte in partes_pdf(r.json().get("payload", {})):
                try:
                    out.append(
                        (
                            parte["filename"],
                            descargar_adjunto(token, message_id, parte["attachment_id"]),
                        )
                    )
                except Exception:
                    continue
    except Exception:
        return out
    return out
