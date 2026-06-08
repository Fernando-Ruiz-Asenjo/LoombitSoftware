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
    """Envía un correo via Gmail API directamente. Soporta adjuntos via attachment_path.

    El correo (asunto y cuerpo, con saludo y firma) lo redacta el modelo. Aquí solo se normaliza
    el formato de los saltos de línea antes de enviar."""
    try:
        from ..config import get_settings
        from ..skill_blanca_gmail import normalize_email_text, send_email

        receipt = send_email(
            to=to,
            subject=subject,
            body_text=normalize_email_text(body),
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


def candidatos_de_people(results: list) -> list:
    """Parsea `results[]` de People API (searchContacts u otherContacts:search) a Candidatos con
    email. Pública y pura → testeable sin red (así se prueba el camino de 'otros contactos')."""
    from ..recipients import Candidato

    out = []
    for res in results or []:
        p = res.get("person", {})
        names = p.get("names", [{}])
        display_name = names[0].get("displayName", "") if names else ""
        for em in p.get("emailAddresses", []):
            if em.get("value"):
                out.append(Candidato(display_name, em["value"], "google"))
    return out


def _people_search(client, headers: dict, endpoint: str, name: str, out: list) -> None:
    """Llama a un endpoint de búsqueda de People API y añade los candidatos con email a `out`."""
    try:
        resp = client.get(
            f"https://people.googleapis.com/v1/{endpoint}",
            headers=headers,
            params={"query": name, "readMask": "names,emailAddresses", "pageSize": 10},
        )
        if resp.status_code == 200:
            out.extend(candidatos_de_people(resp.json().get("results", [])))
    except Exception:
        pass


def _contacts_find(name: str) -> str:
    """Resuelve un destinatario por nombre: fusiona Google Contacts + memoria FIABLE, rankea por
    confianza y frecuencia (F3) y devuelve `mejor` (el más probable) + `estado` (ambiguo → pregunta).
    Excluye contactos `auto` (capturados de envíos): no son verdad confirmada."""
    from ..recipients import Candidato, resolver_destinatario

    candidatos: list[Candidato] = []
    aviso = ""

    # 1) Google Contacts (best-effort: sin OAuth, seguimos solo con memoria)
    try:
        import httpx

        from ..config import get_settings
        from ..skill_blanca_oauth import fresh_access_token

        token = fresh_access_token(get_settings(), "google")
        if token:
            headers = {"Authorization": f"Bearer {token}"}
            with httpx.Client(timeout=10) as client:
                # 1) Libreta de contactos. 2) "Otros contactos" (gente a la que has escrito): ahí
                # vive el email de un destinatario habitual no guardado. Su API exige un warm-up
                # (una llamada con query vacía) o devuelve vacío en frío.
                _people_search(client, headers, "people:searchContacts", name, candidatos)
                try:
                    client.get(
                        "https://people.googleapis.com/v1/otherContacts:search",
                        headers=headers,
                        params={"query": "", "readMask": "names,emailAddresses"},
                    )
                    _people_search(client, headers, "otherContacts:search", name, candidatos)
                except Exception as exc:
                    # 403 si falta el scope contacts.other.readonly (hay que re-autorizar Google)
                    aviso = f"otros contactos no disponibles ({exc}); re-autoriza Google"
        else:
            aviso = "Google OAuth no conectado (solo memoria)."
    except Exception as exc:
        aviso = f"Google Contacts no disponible: {exc}"

    # 2) Memoria: SOLO contactos cacheados de Google (source="google"). NO los 'auto' (capturados
    # de envíos) NI los 'manual' heredados sin procedencia real — en la práctica son auto-capturas
    # mal etiquetadas (la raíz del bug `jana.espinal`). El directorio fiable es Google.
    try:
        from ..agent.memory import get_memory

        for c in get_memory().find_contact(name):
            if c.source == "google" and c.email:
                candidatos.append(Candidato(c.name, c.email, c.source, c.times_contacted))
    except Exception:
        pass

    estado, mejor, ranking = resolver_destinatario(candidatos)
    return json.dumps(
        {
            "ok": True,
            "query": name,
            "estado": estado,  # resuelto | ambiguo | vacio
            "mejor": ({"name": mejor.name, "email": mejor.email} if mejor else None),
            "contacts": [{"name": c.name, "email": c.email} for c in ranking],
            "aviso": aviso,
        },
        ensure_ascii=False,
    )


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
