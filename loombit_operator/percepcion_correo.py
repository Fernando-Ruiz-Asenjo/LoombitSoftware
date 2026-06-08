"""
percepcion_correo.py — destilar SEÑALES accionables de la bandeja (local, determinista).

El telar y el brief ya leían correos, pero solo veían lo evidente (no leídos de contactos
conocidos, agenda de HOY). Esto destila lo que un buen administrativo "pesca" leyendo: una
**reunión/cita acordada en un correo** ("quedamos el jueves a las 9", "te llamo el 12/06"),
aunque el remitente no sea un contacto guardado y aunque NO esté todavía en el calendario.

Regla nº 1 (no mentir): es conservador. Solo afirma una reunión si hay una **palabra de cita** Y un
**día reconocible** (día de la semana, "mañana", o fecha explícita). La hora es opcional. Lo
detectado se marca SIEMPRE como "según un correo de X" — es una propuesta para que el humano agende,
no un hecho. Nada de esto sale de la máquina.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

# Palabra que, junto a un día, sugiere una cita real (no una mención cualquiera de un día).
_PALABRAS_REUNION = (
    "reunión",
    "reunion",
    "reunirnos",
    "quedamos",
    "quedar",
    "nos vemos",
    "vernos",
    "cita",
    "llamada",
    "te llamo",
    "videollamada",
    "videoconferencia",
    "call",
    "meeting",
    "kickoff",
    "kick-off",
    "demo",
    "entrevista",
    "visita",
    "café",
)

_DIAS_SEMANA = {
    "lunes": 0,
    "martes": 1,
    "miércoles": 2,
    "miercoles": 2,
    "jueves": 3,
    "viernes": 4,
    "sábado": 5,
    "sabado": 5,
    "domingo": 6,
}
_NOMBRE_DIA = {
    0: "lunes",
    1: "martes",
    2: "miércoles",
    3: "jueves",
    4: "viernes",
    5: "sábado",
    6: "domingo",
}

_MESES = (
    "enero febrero marzo abril mayo junio julio agosto "
    "septiembre setiembre octubre noviembre diciembre"
).split()

_RE_FECHA_NUM = re.compile(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b")
_RE_FECHA_TXT = re.compile(r"\b(\d{1,2})\s+de\s+([a-záéíóú]+)\b", re.I)

# Horas: "a las 9", "a las 9:30", "09.00", "9h", "9 de la tarde".
_RE_HORA_ALAS = re.compile(r"\ba\s+las\s+(\d{1,2})(?:[:.h](\d{2}))?", re.I)
_RE_HORA_HM = re.compile(r"\b(\d{1,2})[:.h](\d{2})\b")
_RE_HORA_SUELTA = re.compile(r"\b(\d{1,2})\s*(?:h|horas)\b", re.I)
_RE_FRANJA = re.compile(r"de\s+la\s+(mañana|tarde|noche)", re.I)


def _email_de(header: str) -> str:
    m = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", header or "")
    return m.group(0) if m else ""


def _nombre_de(header: str) -> str:
    h = (header or "").strip()
    if "<" in h:
        nombre = h.split("<", 1)[0].strip().strip('"')
        if nombre:
            return nombre
    em = _email_de(h)
    return em.split("@")[0] if em else h


def _fecha_explicita(texto: str, hoy: date) -> str | None:
    m = _RE_FECHA_NUM.search(texto)
    if m:
        d, mth = int(m.group(1)), int(m.group(2))
        y = int(m.group(3)) if m.group(3) else hoy.year
        if m.group(3) and y < 100:
            y += 2000
        try:
            return date(y, mth, d).isoformat()
        except ValueError:
            return None
    m = _RE_FECHA_TXT.search(texto)
    if m:
        mes = m.group(2).lower()
        if mes in _MESES:
            mth = _MESES.index(mes) + 1
            if mth >= 13:  # "setiembre" duplica septiembre
                mth -= 1
            try:
                return date(hoy.year, mth, int(m.group(1))).isoformat()
            except ValueError:
                return None
    return None


def _proxima_fecha_dia(idx: int, hoy: date) -> date:
    """Próxima fecha (incluido hoy) cuyo día de la semana sea `idx` (lunes=0)."""
    return hoy + timedelta(days=(idx - hoy.weekday()) % 7)


def dia_en(texto: str, hoy: date) -> tuple[str | None, str]:
    """(fecha ISO, etiqueta humana) del día citado en el texto, o (None, '') si no hay día claro.
    Prioriza la fecha explícita; si no, día de la semana; si no, hoy/mañana/pasado mañana."""
    iso = _fecha_explicita(texto, hoy)
    if iso:
        d = date.fromisoformat(iso)
        return iso, f"el {d.day}/{d.month}"

    low = texto.lower()
    for nombre, idx in _DIAS_SEMANA.items():
        if re.search(rf"\b{nombre}\b", low):
            return _proxima_fecha_dia(idx, hoy).isoformat(), f"el {_NOMBRE_DIA[idx]}"

    if re.search(r"\bpasado\s+mañana\b", low):
        return (hoy + timedelta(days=2)).isoformat(), "pasado mañana"
    # "mañana" como DÍA (no "de la mañana", que es franja horaria)
    if re.search(r"(?<!de la )\bmañana\b", low):
        return (hoy + timedelta(days=1)).isoformat(), "mañana"
    if re.search(r"\bhoy\b", low):
        return hoy.isoformat(), "hoy"
    return None, ""


def hora_en(texto: str) -> str:
    """'HH:MM' de la hora citada, o '' si no hay. Normaliza tarde/noche a 24h."""
    m = _RE_HORA_ALAS.search(texto) or _RE_HORA_HM.search(texto) or _RE_HORA_SUELTA.search(texto)
    if not m:
        return ""
    hh = int(m.group(1))
    mm = int(m.group(2)) if m.lastindex and m.lastindex >= 2 and m.group(2) else 0
    franja = _RE_FRANJA.search(texto)
    if franja and franja.group(1).lower() in ("tarde", "noche") and hh < 12:
        hh += 12
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        return ""
    return f"{hh:02d}:{mm:02d}"


def detectar_reuniones(correos: list[dict], hoy: date) -> list[dict]:
    """Reuniones/citas acordadas en los correos. Cada una: {asunto, de, email, fecha, hora, cuando,
    snippet}. Conservador: necesita palabra de cita + día reconocible; la hora es opcional. Dedup
    por (de, fecha, hora). Solo días de hoy en adelante (una cita pasada no se propone agendar)."""
    vistos: set = set()
    out: list[dict] = []
    for c in correos:
        blob = f"{c.get('subject', '')} {c.get('snippet', '')}"
        low = blob.lower()
        if not any(p in low for p in _PALABRAS_REUNION):
            continue
        fecha, cuando = dia_en(blob, hoy)
        if not fecha or fecha < hoy.isoformat():
            continue
        hora = hora_en(blob)
        de = _nombre_de(c.get("from", ""))
        clave = (de.lower(), fecha, hora)
        if clave in vistos:
            continue
        vistos.add(clave)
        out.append(
            {
                "asunto": c.get("subject", ""),
                "de": de,
                "email": _email_de(c.get("from", "")),
                "fecha": fecha,
                "hora": hora,
                "cuando": f"{cuando} a las {hora}" if hora else cuando,
                "snippet": (c.get("snippet", "") or "")[:160],
            }
        )
    return out
