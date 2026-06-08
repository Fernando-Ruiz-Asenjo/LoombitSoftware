"""
routers/home.py — contexto del home estilo Google Workspace: procesos diarios + contactos habituales.

Alimenta el panel izquierdo de la UI. Los **contactos habituales** se sacan analizando a quién
escribes más en Gmail (carpeta Enviados) — eso necesita el scope `gmail.readonly` (re-autorizar);
mientras tanto cae a la memoria/libreta. Honesto: si no hay datos, lo dice (no inventa contactos).
"""

from __future__ import annotations

import re
from collections import Counter

from fastapi import APIRouter

router = APIRouter(tags=["home"])

# Procesos diarios de un operador administrativo → cada uno prefil­la una tarea en el chat.
PROCESOS_DIARIOS = [
    {"label": "Redactar correo", "icon": "✉️", "prompt": "Quiero enviar un correo a "},
    {
        "label": "Resumen del día",
        "icon": "📋",
        "prompt": "Hazme un resumen de hoy: tareas, vencimientos y el foco recomendado",
        "auto": True,
    },
    {"label": "Crear evento", "icon": "📅", "prompt": "Crea un evento en mi calendario: "},
    {"label": "Registrar factura", "icon": "🧾", "prompt": "Registra una factura nueva: "},
    {
        "label": "Reclamar cobro",
        "icon": "💶",
        "prompt": "Prepara la reclamación de un cobro pendiente",
    },
    {"label": "Conciliación bancaria", "icon": "🏦", "prompt": "Concilia mi extracto bancario"},
    {"label": "Buscar en el correo", "icon": "🔎", "prompt": "Busca en mi correo: "},
]

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def _parse_destinatarios(to_header: str) -> list[tuple[str, str]]:
    salida = []
    for parte in to_header.split(","):
        m = _EMAIL_RE.search(parte)
        if not m:
            continue
        email = m.group(0).lower()
        nombre = parte.split("<")[0].strip().strip('"') if "<" in parte else email.split("@")[0]
        salida.append((nombre, email))
    return salida


def _contactos_de_gmail(settings, max_msgs: int = 40) -> list[dict]:
    """Analiza tus Enviados y rankea a quién más escribes. Best-effort: [] sin scope gmail.readonly."""
    try:
        import httpx

        from ..skill_blanca_oauth import fresh_access_token

        token = fresh_access_token(settings, "google")
        if not token:
            return []
        h = {"Authorization": f"Bearer {token}"}
        cnt: Counter = Counter()
        nombres: dict[str, str] = {}
        with httpx.Client(timeout=12) as c:
            r = c.get(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages",
                headers=h,
                params={"q": "in:sent", "maxResults": max_msgs},
            )
            if r.status_code != 200:  # 403 si falta gmail.readonly → re-autorizar
                return []
            for m in r.json().get("messages", [])[:max_msgs]:
                mr = c.get(
                    f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{m['id']}",
                    headers=h,
                    params={"format": "metadata", "metadataHeaders": ["To"]},
                )
                if mr.status_code != 200:
                    continue
                headers = {
                    x["name"]: x["value"] for x in mr.json().get("payload", {}).get("headers", [])
                }
                for nombre, email in _parse_destinatarios(headers.get("To", "")):
                    cnt[email] += 1
                    nombres.setdefault(email, nombre or email.split("@")[0])
        return [
            {"name": nombres[email], "email": email, "veces": n} for email, n in cnt.most_common(8)
        ]
    except Exception:
        return []


def _contactos_de_memoria() -> list[dict]:
    """Fallback: contactos fiables de la memoria, rankeados por frecuencia de trato."""
    from ..agent.memory import get_memory

    cs = [c for c in get_memory().contacts if c.source in ("google", "manual") and c.email]
    cs.sort(key=lambda c: c.times_contacted, reverse=True)
    return [
        {"name": c.name or c.email.split("@")[0], "email": c.email, "veces": c.times_contacted}
        for c in cs[:8]
    ]


@router.get("/home/context")
def home_context() -> dict:
    """Procesos diarios + contactos habituales para el panel izquierdo."""
    from ..config import get_settings

    contactos = _contactos_de_gmail(get_settings())
    fuente = "gmail"
    if not contactos:
        contactos = _contactos_de_memoria()
        fuente = "memoria" if contactos else "vacio"
    aviso = ""
    if fuente != "gmail":
        aviso = "Re-autoriza Google (Conectar Google) para que analice tu correo y sepa a quién escribes más."
    return {
        "procesos_diarios": PROCESOS_DIARIOS,
        "contactos_habituales": contactos,
        "fuente_contactos": fuente,
        "aviso": aviso,
    }
