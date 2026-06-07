"""
Tools de conectores para el agente — acceso directo a APIs sin pasar por el navegador.

Llaman directamente a las funciones Python de cada conector (no via HTTP),
por lo que son mucho más rápidas que Computer Use para tareas conocidas.

Tools registradas:
  gmail_send          — envía un correo via Gmail API
  gmail_search        — busca correos (para contexto/historial)
  calendar_create     — crea un evento en Google Calendar
  contacts_find       — busca un contacto por nombre para obtener su email

🟡 Estado: implementadas, requieren OAuth Google activo para funcionar.
   Sin OAuth devuelven un mensaje de error claro indicando qué falta.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from .registry import ToolDefinition, tool_registry

# ── gmail_send ────────────────────────────────────────────────────────────────


def _gmail_send(
    to: str,
    subject: str,
    body: str,
    cc: str = "",
    attachment_path: str = "",
) -> str:
    """Envía un correo via Gmail API directamente. Soporta adjuntos via attachment_path."""
    try:
        from ..skill_blanca_gmail import send_email
        from ..config import get_settings

        receipt = send_email(
            to=to,
            subject=subject,
            body_text=body,
            cc=cc,
            attachment_path=attachment_path,
            settings=get_settings(),
        )
        return json.dumps(
            {
                "ok": True,
                "message_id": receipt.get("message_id", ""),
                "to": to,
                "subject": subject,
                "sent_at": receipt.get("sent_at", datetime.now(UTC).isoformat()),
                "receipt_path": receipt.get("receipt_path", ""),
            },
            ensure_ascii=False,
        )
    except Exception as exc:
        msg = str(exc)
        if "no_token" in msg or "no está conectado" in msg or "token" in msg.lower():
            return json.dumps(
                {
                    "ok": False,
                    "error": "Google OAuth no está conectado. Necesitas autorizar en /skill-blanca/oauth/google/authorize",
                },
                ensure_ascii=False,
            )
        return json.dumps({"ok": False, "error": msg}, ensure_ascii=False)


# ── gmail_search ──────────────────────────────────────────────────────────────


def _gmail_search(query: str, max_results: int = 5) -> str:
    """Busca correos en Gmail para obtener contexto o historial de conversación."""
    try:
        from ..skill_blanca_oauth import fresh_access_token
        from ..config import get_settings
        import httpx

        settings = get_settings()
        token = fresh_access_token(settings, "google")
        if not token:
            return json.dumps(
                {
                    "ok": False,
                    "error": "Google OAuth no conectado. Autoriza en /skill-blanca/oauth/google/authorize",
                },
                ensure_ascii=False,
            )

        params = {"q": query, "maxResults": max_results, "fields": "messages(id,threadId)"}
        with httpx.Client(timeout=10) as client:
            resp = client.get(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages",
                headers={"Authorization": f"Bearer {token}"},
                params=params,
            )
        if resp.status_code != 200:
            return json.dumps(
                {"ok": False, "error": f"Gmail API {resp.status_code}: {resp.text[:200]}"},
                ensure_ascii=False,
            )

        messages = resp.json().get("messages", [])
        if not messages:
            return json.dumps(
                {"ok": True, "count": 0, "messages": [], "query": query}, ensure_ascii=False
            )

        # Obtener snippets de los primeros mensajes
        results = []
        for msg in messages[:max_results]:
            msg_resp = client.get(
                f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg['id']}",
                headers={"Authorization": f"Bearer {token}"},
                params={"format": "metadata", "metadataHeaders": ["Subject", "From", "To", "Date"]},
            )
            if msg_resp.status_code == 200:
                data = msg_resp.json()
                headers = {
                    h["name"]: h["value"] for h in data.get("payload", {}).get("headers", [])
                }
                results.append(
                    {
                        "id": msg["id"],
                        "subject": headers.get("Subject", ""),
                        "from": headers.get("From", ""),
                        "to": headers.get("To", ""),
                        "date": headers.get("Date", ""),
                        "snippet": data.get("snippet", ""),
                    }
                )

        return json.dumps(
            {"ok": True, "count": len(results), "query": query, "messages": results},
            ensure_ascii=False,
        )

    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)


# ── calendar_create ───────────────────────────────────────────────────────────


def _calendar_create(
    title: str,
    start_iso: str,
    duration_minutes: int = 60,
    description: str = "",
    location: str = "",
    attendees: str = "",
) -> str:
    """Crea un evento en Google Calendar via API directamente."""
    try:
        from ..skill_blanca_calendar import create_event
        from ..config import get_settings

        # attendees puede venir como string separado por comas
        attendees_list = [a.strip() for a in attendees.split(",") if a.strip()] if attendees else []

        receipt = create_event(
            summary=title,
            start_iso=start_iso,
            duration_minutes=duration_minutes,
            description=description,
            location=location,
            attendees=attendees_list,
            settings=get_settings(),
        )
        return json.dumps(
            {
                "ok": True,
                "event_id": receipt.get("event_id", ""),
                "html_link": receipt.get("html_link", ""),
                "title": title,
                "start": start_iso,
                "receipt_path": receipt.get("receipt_path", ""),
            },
            ensure_ascii=False,
        )
    except Exception as exc:
        msg = str(exc)
        if "no_token" in msg or "no está conectado" in msg or "token" in msg.lower():
            return json.dumps(
                {
                    "ok": False,
                    "error": "Google OAuth no conectado. Autoriza en /skill-blanca/oauth/google/authorize",
                },
                ensure_ascii=False,
            )
        return json.dumps({"ok": False, "error": msg}, ensure_ascii=False)


# ── contacts_find ─────────────────────────────────────────────────────────────


def _contacts_find(name: str) -> str:
    """Busca un contacto por nombre en Google Contacts para obtener su email."""
    try:
        from ..skill_blanca_oauth import fresh_access_token
        from ..config import get_settings
        import httpx

        settings = get_settings()
        token = fresh_access_token(settings, "google")
        if not token:
            return json.dumps(
                {
                    "ok": False,
                    "error": "Google OAuth no conectado.",
                },
                ensure_ascii=False,
            )

        with httpx.Client(timeout=10) as client:
            resp = client.get(
                "https://people.googleapis.com/v1/people:searchContacts",
                headers={"Authorization": f"Bearer {token}"},
                params={"query": name, "readMask": "names,emailAddresses", "pageSize": 5},
            )

        if resp.status_code != 200:
            return json.dumps(
                {"ok": False, "error": f"Contacts API {resp.status_code}"}, ensure_ascii=False
            )

        results = []
        for person in resp.json().get("results", []):
            p = person.get("person", {})
            names = p.get("names", [{}])
            emails = p.get("emailAddresses", [])
            display_name = names[0].get("displayName", "") if names else ""
            for email_entry in emails:
                results.append(
                    {
                        "name": display_name,
                        "email": email_entry.get("value", ""),
                    }
                )

        return json.dumps({"ok": True, "query": name, "contacts": results}, ensure_ascii=False)

    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)


# ── Registro ──────────────────────────────────────────────────────────────────

tool_registry.register(
    ToolDefinition(
        name="gmail_send",
        description=(
            "Envia correo via Gmail API (requiere OAuth). Usar en vez de abrir navegador. "
            "Para adjuntar una captura de pantalla: primero llama save_screenshot_to_file, "
            "luego pasa la ruta devuelta en attachment_path."
        ),
        parameters={
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
                "cc": {"type": "string", "default": ""},
                "attachment_path": {
                    "type": "string",
                    "default": "",
                    "description": "Ruta local de fichero a adjuntar (PNG, PDF, etc.). Opcional.",
                },
            },
            "required": ["to", "subject", "body"],
        },
        fn=_gmail_send,
        requires_approval=True,
        safety_class="assisted",
        category="connector",
    )
)

tool_registry.register(
    ToolDefinition(
        name="gmail_search",
        description="Busca correos en Gmail para contexto/historial. query estilo Gmail.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_results": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
        fn=_gmail_search,
        category="connector",
    )
)

tool_registry.register(
    ToolDefinition(
        name="calendar_create",
        description="Crea evento en Google Calendar via API. start_iso en ISO 8601.",
        parameters={
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "start_iso": {"type": "string"},
                "duration_minutes": {"type": "integer", "default": 60},
                "description": {"type": "string", "default": ""},
                "location": {"type": "string", "default": ""},
                "attendees": {"type": "string", "default": ""},
            },
            "required": ["title", "start_iso"],
        },
        fn=_calendar_create,
        requires_approval=True,
        safety_class="assisted",
        category="connector",
    )
)

tool_registry.register(
    ToolDefinition(
        name="contacts_find",
        description="Busca email de contacto por nombre en Google Contacts.",
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
            },
            "required": ["name"],
        },
        fn=_contacts_find,
        category="connector",
    )
)
