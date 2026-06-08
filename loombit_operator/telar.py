"""
telar.py — "La tela de la mañana": el contexto del día tejido en HILOS accionables.

La idea (El Telar, Investigación 7): al abrir Loombit, antes de que pidas nada, ves lo
importante de hoy y lo que YA está preparado — un clic, no trabajo. Teje en una sola tela los
hilos que ya percibimos por separado:

  - 📅 tu agenda de hoy (calendar)                → eventos_de_hoy
  - 💰 cobros que vencen / vencidos              → CuentasCobrarStore
  - 📨 correos sin responder de tus contactos    → reply-watch (con borrador preparado)
  - ⏰ PLAZOS detectados en tus correos          → _plazos_en_correos (lo nuevo: se adelanta)
  - ✅ aprobaciones pendientes                    → AgentStore

Cada hilo trae su ACCIÓN ya preparada (responder, recordar cobro, agendar el plazo); los
efectos pasan por el agente → aprobación (gate intacto). Determinista; el LLM solo narra el
saludo (con fallback). Todas las fuentes son inyectables → testeable sin red ni LLM.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

# Palabras que, junto a una fecha, indican un PLAZO real (no una fecha cualquiera).
_PALABRAS_PLAZO = (
    "antes del",
    "antes de",
    "fecha límite",
    "fecha limite",
    "vence",
    "plazo",
    "deadline",
    "entregar",
    "presentar",
    "hasta el",
    "para el",
    "límite",
)
_MESES = (
    "enero febrero marzo abril mayo junio julio agosto "
    "septiembre setiembre octubre noviembre diciembre"
).split()
# Fechas explícitas: 15/06, 15-06-2026, "15 de junio".
_RE_FECHA_NUM = re.compile(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b")
_RE_FECHA_TXT = re.compile(r"\b(\d{1,2})\s+de\s+([a-záéíóú]+)\b", re.I)


def _saludo(now: datetime) -> str:
    h = now.hour
    if h < 6:
        return "Buenas noches"
    if h < 13:
        return "Buenos días"
    if h < 21:
        return "Buenas tardes"
    return "Buenas noches"


def _email_de(header: str) -> str:
    m = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", header or "")
    return m.group(0) if m else ""


def _nombre_de(header: str) -> str:
    """'Jana <j@x.com>' → 'Jana'; 'j@x.com' → 'j'."""
    h = (header or "").strip()
    if "<" in h:
        nombre = h.split("<", 1)[0].strip().strip('"')
        if nombre:
            return nombre
    em = _email_de(h)
    return em.split("@")[0] if em else h


def _fecha_en(texto: str, hoy: date) -> str | None:
    """Devuelve una fecha ISO si hay una fecha explícita en el texto; si no, None."""
    m = _RE_FECHA_NUM.search(texto)
    if m:
        d, mth = int(m.group(1)), int(m.group(2))
        y = int(m.group(3) or hoy.year) if m.group(3) else hoy.year
        if m.group(3) and y < 100:
            y += 2000
        try:
            return date(y, mth, d).isoformat()
        except ValueError:
            return None
    m = _RE_FECHA_TXT.search(texto)
    if m:
        d = int(m.group(1))
        mes = m.group(2).lower()
        if mes in _MESES:
            mth = _MESES.index(mes) + 1
            if mth >= 13:  # "setiembre" duplica septiembre
                mth -= 1
            try:
                return date(hoy.year, mth, d).isoformat()
            except ValueError:
                return None
    return None


def _plazos_en_correos(correos: list[dict], hoy: date) -> list[dict]:
    """Detecta PLAZOS en los correos: una palabra de plazo + una fecha explícita. Conservador
    (si no hay ambos, no inventa). Devuelve {asunto, de, fecha, frase}."""
    out: list[dict] = []
    for c in correos:
        blob = f"{c.get('subject', '')} {c.get('snippet', '')}"
        low = blob.lower()
        if not any(p in low for p in _PALABRAS_PLAZO):
            continue
        fecha = _fecha_en(blob, hoy)
        if not fecha:
            continue
        out.append(
            {
                "asunto": c.get("subject", ""),
                "de": _nombre_de(c.get("from", "")),
                "fecha": fecha,
                "snippet": c.get("snippet", "")[:140],
            }
        )
    return out


# Calendario fiscal del autónomo (España). Fechas ESTÁNDAR de presentación (un festivo puede
# moverlas → la acción prepara un BORRADOR, no presenta; el humano confirma en la AEAT). Públicas.
_FISCAL = [
    (1, 30, "303 · 390 · 130 · 190", "4º trimestre y resumen anual"),
    (4, 20, "303 · 130 · 111 · 115", "1er trimestre"),
    (7, 20, "303 · 130 · 111 · 115", "2º trimestre"),
    (10, 20, "303 · 130 · 111 · 115", "3er trimestre"),
]


def _obligaciones_fiscales(hoy: date, ventana_dias: int = 45) -> list[dict]:
    """Próxima obligación fiscal trimestral dentro de la ventana. Determinista; no inventa:
    fecha estándar + la acción prepara un borrador (el humano presenta)."""
    cands: list[dict] = []
    for anio in (hoy.year, hoy.year + 1):
        for mes, dia, modelos, periodo in _FISCAL:
            try:
                f = date(anio, mes, dia)
            except ValueError:
                continue
            dias = (f - hoy).days
            if 0 <= dias <= ventana_dias:
                cands.append(
                    {"fecha": f.isoformat(), "dias": dias, "modelos": modelos, "periodo": periodo}
                )
    cands.sort(key=lambda c: c["dias"])
    return cands[:1]


def _hilo(tipo: str, icono: str, titulo: str, urgencia: int, accion: dict, **extra: Any) -> dict:
    return {
        "tipo": tipo,
        "icono": icono,
        "titulo": titulo,
        "urgencia": urgencia,
        "accion": accion,
        **extra,
    }


def tejer_dia(
    *,
    settings: Any = None,
    now: datetime | None = None,
    eventos: list[dict] | None = None,
    correos: list[dict] | None = None,
    inbox: list[dict] | None = None,
    vencidas: list | None = None,
    proximas: list | None = None,
    aprobaciones: int | None = None,
) -> dict[str, Any]:
    """Teje la tela del día. Todas las fuentes son inyectables (None = se obtienen de verdad).

    Devuelve `{saludo, hilos[], resumen, meta}`. Cada hilo lleva su acción preparada.
    """
    ahora = now or datetime.now()
    hoy = ahora.date()
    hilos: list[dict] = []

    # Fuentes reales (best-effort; si una falla, no aporta hilo — nunca inventa).
    if eventos is None:
        eventos = _fuente_eventos(settings, ahora)
    if correos is None:
        correos = _fuente_correos(settings)
    if inbox is None:
        inbox = _fuente_inbox(settings)
    if vencidas is None or proximas is None:
        v, p = _fuente_cobros(settings)
        vencidas = vencidas if vencidas is not None else v
        proximas = proximas if proximas is not None else p
    if aprobaciones is None:
        aprobaciones = _fuente_aprobaciones()

    # 📅 Agenda de hoy
    for ev in eventos[:6]:
        hora = str(ev.get("start", ""))[11:16]
        titulo = f"{hora} · {ev.get('summary', '(evento)')}".strip(" ·")
        hilos.append(
            _hilo("agenda", "📅", titulo, urgencia=1, accion={"modo": "navigate", "label": "Ver"})
        )

    # 💰 Cobros
    for cu in (vencidas or [])[:6]:
        imp = getattr(cu, "importe", 0)
        cliente = getattr(cu, "cliente", "")
        hilos.append(
            _hilo(
                "cobro",
                "💰",
                f"{cliente} · {imp:.0f} € VENCIDA",
                urgencia=2,
                accion={
                    "modo": "agent_task",
                    "label": "Preparar recordatorio",
                    "task": f"Prepara un recordatorio de cobro cordial para {cliente} por {imp:.0f} € (factura vencida), en mi nombre.",
                },
            )
        )
    for cu in (proximas or [])[:4]:
        imp = getattr(cu, "importe", 0)
        cliente = getattr(cu, "cliente", "")
        hilos.append(
            _hilo(
                "cobro",
                "💰",
                f"{cliente} · {imp:.0f} € vence pronto",
                urgencia=1,
                accion={
                    "modo": "agent_task",
                    "label": "Preparar aviso",
                    "task": f"Prepara un aviso amable de vencimiento próximo a {cliente} por {imp:.0f} €, en mi nombre.",
                },
            )
        )

    # 🧾 Calendario fiscal del autónomo — siempre sabe tu próximo impuesto (el moat español)
    for ob in _obligaciones_fiscales(hoy):
        urg = 2 if ob["dias"] <= 10 else 1
        hilos.append(
            _hilo(
                "fiscal",
                "🧾",
                f"Impuestos {ob['periodo']} ({ob['modelos']}) → {ob['fecha']} ({ob['dias']}d)",
                urgencia=urg,
                accion={
                    "modo": "agent_task",
                    "label": "Preparar borrador",
                    "task": f"Prepara un borrador del modelo 303 (IVA) del {ob['periodo']} a partir de mis facturas; yo lo reviso y lo presento en la AEAT. Avísame si falta algún dato.",
                },
                detalle="Fecha estándar de presentación; confirma festivos en la AEAT.",
            )
        )

    # 📨 Correos sin responder (con borrador a un clic)
    for c in (correos or [])[:6]:
        de = _nombre_de(c.get("from", ""))
        email = _email_de(c.get("from", ""))
        asunto = c.get("subject", "")
        hilos.append(
            _hilo(
                "correo",
                "📨",
                f"{de} te escribió: «{asunto[:50]}»",
                urgencia=1,
                accion={
                    "modo": "agent_task",
                    "label": "Redactar respuesta",
                    "task": f"Responde al correo de {de} ({email}) «{asunto}». Su mensaje: «{c.get('snippet', '')[:200]}». Redacta una respuesta breve y natural en mi nombre.",
                },
            )
        )

    # ⏰ Plazos detectados — escanea correos de contactos + bandeja reciente (gestoría/AEAT/quien
    # sea es justo donde viven los plazos). Dedup por asunto+fecha.
    _vistos: set = set()
    _plazos: list[dict] = []
    for pl in _plazos_en_correos((correos or []) + (inbox or []), hoy):
        clave = (pl["asunto"], pl["fecha"])
        if clave not in _vistos:
            _vistos.add(clave)
            _plazos.append(pl)
    for pl in _plazos[:5]:
        hilos.append(
            _hilo(
                "plazo",
                "⏰",
                f"Plazo: «{pl['asunto'][:40]}» → {pl['fecha']}",
                urgencia=2,
                accion={
                    "modo": "agent_task",
                    "label": "Agendar",
                    "task": f"Crea un evento en mi calendario el {pl['fecha']} titulado «{pl['asunto'][:60]}» (plazo detectado en un correo de {pl['de']}).",
                },
                detalle=pl["snippet"],
            )
        )

    # ✅ Aprobaciones pendientes
    if aprobaciones:
        hilos.append(
            _hilo(
                "aprobacion",
                "✅",
                f"{aprobaciones} acción(es) esperando tu aprobación",
                urgencia=2,
                accion={"modo": "navigate", "label": "Revisar"},
            )
        )

    hilos.sort(key=lambda h: -h["urgencia"])

    return {
        "saludo": _saludo(ahora),
        "hilos": hilos,
        "resumen": _resumen(hilos),
        "meta": {
            "generado": ahora.isoformat(timespec="seconds"),
            "n_hilos": len(hilos),
            "privado": "Nada de esto ha salido de tu máquina.",
        },
    }


def _resumen(hilos: list[dict]) -> str:
    """Una línea humana y cálida (determinista; sin LLM para no depender de él aquí)."""
    if not hilos:
        return "Hoy está despejado. Si surge algo, te aviso."
    urgentes = sum(1 for h in hilos if h["urgencia"] >= 2)
    n = len(hilos)
    base = f"Tienes {n} cosa(s) en el telar de hoy"
    if urgentes:
        base += f", {urgentes} que pide(n) atención"
    return base + ". Te lo he dejado preparado — un clic y listo."


# ── Fuentes reales (aisladas para que el motor sea testeable sin ellas) ─────────
def _fuente_eventos(settings: Any, ahora: datetime) -> list[dict]:
    try:
        from .skill_blanca_calendar_read import eventos_de_hoy

        return eventos_de_hoy(settings=settings, now=ahora)
    except Exception:
        return []


def _fuente_correos(settings: Any) -> list[dict]:
    try:
        from types import SimpleNamespace

        from .config import get_settings
        from .routers.home import _contactos_de_gmail
        from .routine_executors import _buscar_respuestas
        from .skill_blanca_oauth import fresh_access_token

        st = settings or get_settings()
        token = fresh_access_token(st, "google")
        if not token:
            return []
        contactos = [
            SimpleNamespace(name=c["name"], email=c["email"]) for c in _contactos_de_gmail(st)
        ]
        return _buscar_respuestas(token, contactos)
    except Exception:
        return []


def _fuente_inbox(settings: Any, dias: int = 6, maximo: int = 18) -> list[dict]:
    """Correos recientes SIN LEER de toda la bandeja (read-only) — para detectar plazos
    vengan de quien vengan (gestoría, AEAT, bancos…). Devuelve from/subject/snippet."""
    try:
        import httpx

        from .config import get_settings
        from .skill_blanca_oauth import fresh_access_token

        st = settings or get_settings()
        token = fresh_access_token(st, "google")
        if not token:
            return []
        h = {"Authorization": f"Bearer {token}"}
        out: list[dict] = []
        with httpx.Client(timeout=12) as c:
            r = c.get(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages",
                headers=h,
                params={"q": f"is:unread newer_than:{dias}d", "maxResults": maximo},
            )
            if r.status_code != 200:
                return []
            for m in r.json().get("messages", [])[:maximo]:
                mr = c.get(
                    f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{m['id']}",
                    headers=h,
                    params={"format": "metadata", "metadataHeaders": ["From", "Subject"]},
                )
                if mr.status_code != 200:
                    continue
                data = mr.json()
                hdrs = {x["name"]: x["value"] for x in data.get("payload", {}).get("headers", [])}
                out.append(
                    {
                        "from": hdrs.get("From", ""),
                        "subject": hdrs.get("Subject", ""),
                        "snippet": data.get("snippet", "")[:300],
                    }
                )
        return out
    except Exception:
        return []


def _fuente_cobros(settings: Any) -> tuple[list, list]:
    try:
        from .cuentas_cobrar import CuentasCobrarStore

        cc = CuentasCobrarStore(settings=settings) if settings else CuentasCobrarStore()
        return cc.vencidas(), cc.proximas(7)
    except Exception:
        return [], []


def _fuente_aprobaciones() -> int:
    try:
        from .agent import AgentStatus
        from .agent.run import AgentStore

        return len(AgentStore().list(status=AgentStatus.PENDING_APPROVAL))
    except Exception:
        return 0
