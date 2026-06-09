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


_DIAS_ES = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")


def _cuando_humano(fecha_iso: str, hora: str = "") -> str:
    """'2026-06-11' + '09:00' → 'jueves 11/6 · 09:00'."""
    try:
        d = date.fromisoformat(fecha_iso)
        base = f"{_DIAS_ES[d.weekday()]} {d.day}/{d.month}"
    except ValueError:
        base = fecha_iso
    return f"{base} · {hora}" if hora else base


_ICONO_ASUNTO = {"reunion": "📆", "notificacion": "⚠️", "plazo": "⏰", "gestion": "📝"}
_ESTADO_TXT = {
    "confirmada": "✅ confirmada por ambos",
    "requiere_accion": "⚠️ requiere acción",
    "pendiente": "pendiente de respuesta",
}


def _hilo_asunto(a: dict) -> dict:
    """Convierte un asunto COMPRENDIDO (de `comprension`) en un hilo del telar, con su contexto."""
    tipo = a.get("tipo", "gestion")
    if tipo == "reunion":
        quien = f"con {a['con']}" if a.get("con") else ""
        cuando = _cuando_humano(a["fecha"], a.get("hora", "")) if a.get("fecha") else ""
        titulo = f"Reunión {quien}" + (f" · {cuando}" if cuando else "")
    else:
        titulo = a.get("titulo", "Asunto")
    partes = []
    if a.get("lugar"):
        partes.append(f"📍 {a['lugar']}")
    if a.get("estado") in _ESTADO_TXT:
        partes.append(_ESTADO_TXT[a["estado"]])
    if a.get("resumen"):
        partes.append(a["resumen"])
    if a.get("accion"):
        accion = {
            "modo": "agent_task",
            "label": "Gestionar",
            "task": (
                f"{a['accion']} (asunto: «{a.get('origen', '')}»). Prepárame lo necesario; "
                "no envíes ni ejecutes nada externo sin que lo apruebe."
            ),
        }
    else:
        accion = {"modo": "navigate", "label": "Ver"}
    return _hilo(
        tipo,
        _ICONO_ASUNTO.get(tipo, "•"),
        titulo.replace("  ", " ").strip(),
        urgencia=int(a.get("importancia", 2)),
        accion=accion,
        detalle=" · ".join(partes),
        porque=_porque_asunto(tipo, a.get("estado", "")),
    )


def _porque_asunto(tipo: str, estado: str) -> str:
    """El PORQUÉ de un asunto comprendido: una línea causal (por qué está hoy en la tela),
    distinta del detalle. Sale de la cognición (estado/tipo), no de repetir el resumen."""
    if estado == "confirmada":
        return "Confirmada por ambas partes; solo tienes que presentarte."
    if estado == "requiere_accion":
        return "Pide acción tuya — te lo dejo preparado."
    if tipo == "reunion":
        return "Está en tu agenda."
    if tipo == "notificacion":
        return "Notificación que conviene revisar."
    return "Gestión pendiente de cerrar."


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


def _eur(x: float) -> str:
    """Formato monetario español: 1302.86 → '1.302,86'."""
    s = f"{float(x or 0):,.2f}"  # '1,302.86'
    return s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


_TONO_ETAPA = {
    "vence_hoy": ("cordial", "Preparar recordatorio"),
    "recordatorio_amistoso": ("cordial", "Preparar recordatorio"),
    "recordatorio_firme": ("firme pero cordial", "Recordatorio firme"),
    "reclamacion_formal": ("formal", "Reclamación formal"),
}


def _hilo_cobro_vencida(cu: Any, hoy: date) -> dict:
    """Hilo de una factura vencida con su desglose legal (Ley 3/2004): saldo + 40 € de
    compensación + interés de demora con tipo y cita BOE, y el tono según la etapa de escalado.
    Degrada con gracia: si falta/!parsea el vencimiento, cae al recordatorio básico (sin inventar).
    """
    imp = getattr(cu, "importe", 0) or 0
    cliente = getattr(cu, "cliente", "") or ""
    venc = getattr(cu, "vencimiento", "") or ""

    plan = None
    try:
        if venc:
            from .cobros import dunning_plan

            plan = dunning_plan(total=float(imp), due_date=venc, today=hoy.isoformat())
    except Exception:
        plan = None

    # Sin plan (sin vencimiento o no procede reclamar) → recordatorio básico, sin desglose.
    if not plan or plan.get("action") != "reclamar":
        return _hilo(
            "cobro",
            "💰",
            f"{cliente} · {imp:.0f} € VENCIDA",
            urgencia=2,
            accion={
                "modo": "agent_task",
                "label": "Preparar recordatorio",
                "task": (
                    f"Prepara un recordatorio de cobro cordial para {cliente} por {imp:.0f} € "
                    "(factura vencida), en mi nombre."
                ),
            },
            porque="Factura vencida; cuanto antes la reclames, antes cobras.",
        )

    dias = plan["overdue_days"]
    stage = plan["stage"]
    saldo = plan["outstanding"]
    fee = plan.get("fixed_compensation_eur", 0) or 0
    interes = plan.get("interest", {}) or {}
    int_amt = interes.get("amount") or 0

    # Desglose legal honesto, con cita de la fuente.
    partes = [f"Vencida hace {dias} días.", f"Saldo {_eur(saldo)} € + {_eur(fee)} € comp. (art. 8)"]
    cita_interes = ""
    if interes.get("rate_required"):
        partes.append("+ interés de demora a verificar (fuera de la tabla BOE)")
    elif int_amt:
        if interes.get("rate_pct") is not None and interes.get("tramos"):
            tr = interes["tramos"][0]
            tipo_txt = f"{interes['rate_pct']:.2f}".replace(".", ",")
            partes.append(
                f"+ {_eur(int_amt)} € interés demora ({tipo_txt}% {tr['semestre']}, {tr['boe']})"
            )
            cita_interes = (
                f" Conforme a la Ley 3/2004 se podrían añadir {_eur(fee)} € de compensación y "
                f"{_eur(int_amt)} € de interés de demora (tipo legal {tipo_txt}%)."
            )
        else:
            partes.append(f"+ {_eur(int_amt)} € interés demora (por tramos, Ley 3/2004)")
    reclamable = round(float(saldo) + float(fee) + float(int_amt), 2)
    detalle = " ".join(partes) + f" → reclamable ≈ {_eur(reclamable)} €."

    if stage == "via_judicial":
        # No se redacta una reclamación más: se ESCALA a un profesional (el operador no litiga).
        accion = {
            "modo": "agent_task",
            "label": "Escalar a un profesional",
            "task": (
                f"La factura vencida de {cliente} por {imp:.0f} € supera el plazo (vencida hace "
                f"{dias} días). Prepárame un resumen para escalar la vía judicial a un profesional; "
                "recuerda que desde la L.O. 1/2025 hay que intentar/documentar un MASC antes de "
                "demandar. No envíes nada todavía."
            ),
        }
    else:
        tono, label = _TONO_ETAPA.get(stage, ("cordial", "Preparar recordatorio"))
        accion = {
            "modo": "agent_task",
            "label": label,
            "task": (
                f"Prepara un recordatorio de cobro {tono} para {cliente} por {imp:.0f} € "
                f"(factura vencida hace {dias} días; saldo {_eur(saldo)} €).{cita_interes} "
                "Hazlo en mi nombre, claro y respetuoso."
            ),
        }

    return _hilo(
        "cobro",
        "💰",
        f"{cliente} · {imp:.0f} € VENCIDA ({dias}d)",
        urgencia=2,
        accion=accion,
        detalle=detalle,
        porque=f"Vencida hace {dias} días — el recordatorio ya está redactado.",
    )


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
    proximos: list[dict] | None = None,
    asuntos: list[dict] | None = None,
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
    if proximos is None:
        proximos = _fuente_eventos_proximos(settings, ahora)
    if correos is None:
        correos = _fuente_correos(settings)
    if inbox is None:
        # incluir_leidos: una reunión/plazo en un correo YA leído sigue siendo contexto a no perder.
        inbox = _fuente_inbox(settings, incluir_leidos=True)
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
            _hilo(
                "agenda",
                "📅",
                titulo,
                urgencia=1,
                accion={"modo": "navigate", "label": "Ver"},
                porque=(f"Hoy a las {hora}." if hora else "En tu agenda de hoy."),
            )
        )

    # 💰 Cobros — el hilo vencido lleva su desglose LEGAL (saldo + 40 € art. 8 + interés de demora
    # con su tipo y cita BOE) y un tono de reclamación según la etapa. Cifras deterministas (cobros).
    for cu in (vencidas or [])[:6]:
        hilos.append(_hilo_cobro_vencida(cu, hoy))
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
                porque="Vence pronto; un aviso a tiempo evita el retraso.",
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
                porque=f"Vence el {ob['fecha']} ({ob['dias']} días); mejor con margen.",
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
                porque=f"{de} te escribió y sigue sin respuesta.",
            )
        )

    # 🧠 COMPRENSIÓN de la bandeja (Skill D · Comprensión): no extrae datos sueltos — el modelo
    # ENTIENDE los hilos (quién es quién, de qué va, en qué estado: confirmada / requiere acción) y de
    # ahí salen las reuniones (reconciliadas: la palabra del correo manda sobre el calendario), las
    # notificaciones oficiales (Policía/AEAT…) y los plazos. FIABLE: se calcula en SEGUNDO PLANO y se
    # cachea; el telar lee el último resultado bueno y NUNCA muestra el calendario crudo (sin verificar).
    if asuntos is None:
        from .comprension import comprension_cacheada, refrescar_async

        asuntos, _edad = comprension_cacheada()
        if (
            _edad > 600
        ):  # vacío o caducado → refresca en 2º plano (no bloquea el telar ni llama al LLM aquí)
            refrescar_async(
                (correos or []) + (inbox or []), proximos or [], hoy, buscar=_buscar_correos
            )
        if not asuntos and _edad == float("inf"):
            # nunca computado aún: aviso honesto, NUNCA un dato sin verificar
            hilos.append(
                _hilo(
                    "gestion",
                    "🧠",
                    "Verificando tus correos y tu agenda…",
                    urgencia=1,
                    accion={"modo": "navigate", "label": "…"},
                    detalle="Comprendiendo tus conversaciones para no darte nada sin verificar.",
                )
            )
    for a in (asuntos or [])[:6]:
        hilos.append(_hilo_asunto(a))

    # ✅ Aprobaciones pendientes
    if aprobaciones:
        hilos.append(
            _hilo(
                "aprobacion",
                "✅",
                f"{aprobaciones} acción(es) esperando tu aprobación",
                urgencia=2,
                accion={"modo": "navigate", "label": "Revisar"},
                porque="Espera tu visto bueno antes de que salga nada.",
            )
        )

    hilos.sort(key=lambda h: -h["urgencia"])

    return {
        "saludo": _saludo(ahora),
        "usuario": _usuario(),  # BLANCO: el nombre lo pone el owner del usuario, no el código
        "hilos": hilos,
        "resumen": _resumen(hilos),
        "meta": {
            "generado": ahora.isoformat(timespec="seconds"),
            "n_hilos": len(hilos),
            "privado": "Nada de esto ha salido de tu máquina.",
        },
    }


def _usuario() -> str:
    """Nombre del dueño desde la memoria operativa (vacío si aún no se ha personalizado)."""
    try:
        from .agent.memory import get_memory

        return (get_memory().owner.get("name") or "").strip()
    except Exception:
        return ""


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


def _buscar_correos(nombre: str) -> list[dict]:
    """Busca en TODO el Gmail los correos de/sobre `nombre` (para reconciliar reuniones). Read-only."""
    try:
        import json as _json

        from .tools.connectors import _gmail_search

        data = _json.loads(_gmail_search(nombre))
        return data.get("messages", []) if data.get("ok") else []
    except Exception:
        return []


def _fuente_eventos_proximos(settings: Any, ahora: datetime) -> list[dict]:
    """Eventos del calendario en los próximos 7 días (no hoy). Para no perder la reunión del jueves."""
    try:
        from .skill_blanca_calendar_read import eventos_proximos

        return eventos_proximos(settings=settings, now=ahora, dias=7)
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
        propio = _email_propio()  # no te propongas responderte a ti mismo
        contactos = [
            SimpleNamespace(name=c["name"], email=c["email"])
            for c in _contactos_de_gmail(st)
            if (c.get("email") or "").lower() != propio
        ]
        return _buscar_respuestas(token, contactos)
    except Exception:
        return []


def _email_propio() -> str:
    try:
        from .agent.memory import get_memory

        return (get_memory().owner.get("email") or "").strip().lower()
    except Exception:
        return ""


def _fuente_inbox(
    settings: Any, dias: int = 6, maximo: int = 18, incluir_leidos: bool = False
) -> list[dict]:
    """Correos recientes de toda la bandeja (read-only) — para detectar plazos y reuniones vengan
    de quien vengan (gestoría, AEAT, bancos, un proveedor nuevo…). Por defecto solo NO leídos; con
    `incluir_leidos=True` también los ya leídos (una reunión que YA acordaste y leíste sigue siendo
    contexto que no se puede perder). Devuelve from/subject/snippet."""
    try:
        import httpx

        from .config import get_settings
        from .skill_blanca_oauth import fresh_access_token

        st = settings or get_settings()
        token = fresh_access_token(st, "google")
        if not token:
            return []
        h = {"Authorization": f"Bearer {token}"}
        q = f"newer_than:{dias}d" if incluir_leidos else f"is:unread newer_than:{dias}d"
        out: list[dict] = []
        with httpx.Client(timeout=12) as c:
            r = c.get(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages",
                headers=h,
                params={"q": q, "maxResults": maximo},
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
