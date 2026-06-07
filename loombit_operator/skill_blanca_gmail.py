"""
Skill Blanca — Gmail sender.
Envía email via Gmail API REST usando el access_token OAuth de Google.
Guarda recibo local en runtime/local/outbox/ (nunca sube nada a la nube).

🟡 Estado: contrato implementado. Pendiente piloto real contra cuenta de prueba (Fase 1).
   Para pasar a 🟢: ejecutar send_email() con token real y verificar recibo guardado.

Flujo:
  1. load_access_token("google") → obtiene token del store local
  2. compose_message()           → construye el payload RFC 2822 en base64
  3. send_email()                → POST a Gmail API, guarda recibo JSON
  4. recibo devuelto             → { message_id, thread_id, receipt_path, ... }
"""

from __future__ import annotations

import base64
import json
import re
from datetime import UTC, datetime
import mimetypes

from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders
from pathlib import Path
from typing import Any, Callable

import httpx

from .config import AppSettings, get_settings
from .skill_blanca_oauth import fresh_access_token

GMAIL_SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ── Modelos de datos ──────────────────────────────────────────────────────────


def compose_message(
    *,
    to: str,
    subject: str,
    body_text: str,
    body_html: str | None = None,
    cc: str = "",
    reply_to: str = "",
    attachment_path: str = "",
) -> dict[str, Any]:
    """
    Construye el payload listo para Gmail API.
    Devuelve { "raw": "<base64url>" } que se pasa directamente a send_email().
    Soporta attachment_path: ruta a un fichero local (PNG, PDF, etc.) para adjuntar.
    """
    _validate_email(to, "to")
    if cc:
        _validate_email(cc, "cc")
    if not subject.strip():
        raise ValueError("email_subject_required")
    if not body_text.strip():
        raise ValueError("email_body_required")

    # Si hay adjunto, siempre usamos MIMEMultipart mixed
    if attachment_path:
        attach_p = Path(attachment_path)
        if not attach_p.exists():
            raise FileNotFoundError(f"Adjunto no encontrado: {attachment_path}")
        outer: MIMEMultipart = MIMEMultipart("mixed")
        # Parte de texto (con html si existe)
        if body_html:
            alt = MIMEMultipart("alternative")
            alt.attach(MIMEText(body_text, "plain", "utf-8"))
            alt.attach(MIMEText(body_html, "html", "utf-8"))
            outer.attach(alt)
        else:
            outer.attach(MIMEText(body_text, "plain", "utf-8"))
        # Adjunto
        ctype, _ = mimetypes.guess_type(str(attach_p))
        if not ctype:
            ctype = "application/octet-stream"
        maintype, subtype = ctype.split("/", 1)
        with open(attach_p, "rb") as fp:
            att = MIMEBase(maintype, subtype)
            att.set_payload(fp.read())
        encoders.encode_base64(att)
        att.add_header("Content-Disposition", "attachment", filename=attach_p.name)
        outer.attach(att)
        msg: MIMEMultipart | MIMEText = outer
    elif body_html:
        msg = MIMEMultipart("alternative")
        assert isinstance(msg, MIMEMultipart)
        msg.attach(MIMEText(body_text, "plain", "utf-8"))
        msg.attach(MIMEText(body_html, "html", "utf-8"))
    else:
        msg = MIMEText(body_text, "plain", "utf-8")

    msg["To"] = to
    msg["Subject"] = subject
    if cc:
        msg["Cc"] = cc
    if reply_to:
        msg["Reply-To"] = reply_to

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
    return {"raw": raw}


def send_email(
    *,
    to: str,
    subject: str,
    body_text: str,
    body_html: str | None = None,
    cc: str = "",
    reply_to: str = "",
    attachment_path: str = "",
    settings: AppSettings | None = None,
    http_post: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """
    Envía el email via Gmail API y guarda recibo local.
    Requiere token OAuth de Google en el store local.

    Returns:
        receipt — dict con message_id, thread_id, receipt_path y metadatos.
        El receipt se guarda en runtime/local/outbox/<timestamp>_<to>.json
    """
    active = settings or get_settings()
    _check_writes_enabled(active)

    token = fresh_access_token(active, "google")
    if not token:
        raise ValueError(
            "gmail_send_no_token: Google OAuth no está conectado. "
            "Ejecuta /skill-blanca/oauth/google/start primero."
        )

    payload = compose_message(
        to=to,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        cc=cc,
        reply_to=reply_to,
        attachment_path=attachment_path,
    )

    post = http_post or httpx.post
    resp = post(
        GMAIL_SEND_URL,
        json=payload,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=20,
    )

    if resp.status_code == 401:
        raise ValueError(
            "gmail_send_unauthorized: El token de Google ha expirado. "
            "Ejecuta /skill-blanca/oauth/google/start para reconectar."
        )
    if not (200 <= resp.status_code < 300):
        raise ValueError(f"gmail_send_failed:{resp.status_code} — {resp.text[:200]}")

    api_data = resp.json()
    receipt = _build_receipt(
        operation="gmail_send",
        to=to,
        subject=subject,
        cc=cc,
        api_response=api_data,
        outbox_path=active.skill_blanca_connector_outbox_path,
    )
    return receipt


# ── Helpers ───────────────────────────────────────────────────────────────────


def _validate_email(value: str, field: str) -> None:
    if not _EMAIL_RE.match(value.strip()):
        raise ValueError(f"invalid_email_{field}: '{value}'")


def _check_writes_enabled(settings: AppSettings) -> None:
    if not settings.skill_blanca_connector_writes_enabled:
        raise ValueError(
            "gmail_send_disabled: Las escrituras del conector están deshabilitadas. "
            "Activa LOOMBIT_OPERATOR_SKILL_BLANCA_CONNECTOR_WRITES_ENABLED=true en .env"
        )


def _build_receipt(
    *,
    operation: str,
    to: str,
    subject: str,
    cc: str,
    api_response: dict[str, Any],
    outbox_path: Path,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    message_id = str(api_response.get("id", ""))
    thread_id = str(api_response.get("threadId", ""))

    receipt: dict[str, Any] = {
        "operation_type": operation,
        "status": "sent",
        "sent_at": now.isoformat(),
        "to": to,
        "cc": cc,
        "subject": subject,
        "message_id": message_id,
        "thread_id": thread_id,
        "provider": "google_gmail_api",
        "api_response": api_response,
        "dod": "🟢",
    }

    # Guardar recibo local
    safe_to = re.sub(r"[^\w@.-]", "_", to)[:40]
    filename = f"{now.strftime('%Y%m%dT%H%M%SZ')}_{safe_to}.json"
    receipt_path = outbox_path / filename
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")
    receipt["receipt_path"] = str(receipt_path)
    return receipt


def snapshot_outbox(settings: AppSettings | None = None) -> dict[str, Any]:
    """Lista los recibos del outbox local."""
    active = settings or get_settings()
    outbox = active.skill_blanca_connector_outbox_path
    if not outbox.exists():
        return {"outbox_path": str(outbox), "count": 0, "receipts": []}
    files = sorted(outbox.glob("*.json"), reverse=True)
    items = []
    for f in files[:20]:  # últimos 20
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            items.append(
                {
                    "file": f.name,
                    "sent_at": data.get("sent_at", ""),
                    "to": data.get("to", ""),
                    "subject": data.get("subject", ""),
                    "message_id": data.get("message_id", ""),
                    "status": data.get("status", ""),
                }
            )
        except (json.JSONDecodeError, OSError):
            pass
    return {"outbox_path": str(outbox), "count": len(files), "receipts": items}
