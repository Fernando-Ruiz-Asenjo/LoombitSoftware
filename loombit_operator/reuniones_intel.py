"""
reuniones_intel.py — destilación INTELIGENTE de reuniones (Skill D · Reuniones).

La regex no destila: confunde un timestamp con una hora ("13:57"), no entiende "el jueves 11", no
reconcilia el calendario con lo que dice el correo. El que destila es el MODELO leyendo el hilo.

Esto le da al LLM los correos recientes + los eventos del calendario y le pide la reunión REAL
(con quién, fecha, hora, lugar), reconciliando conflictos con una regla clara: **la verdad es lo que
las personas ACUERDAN EXPLÍCITAMENTE en un correo** (su palabra); si el calendario la contradice,
manda el correo y se marca el conflicto (para corregir el calendario, con aprobación del humano).

No inventa: cada reunión va anclada a su origen (correo/evento). Si el LLM no está disponible o
devuelve basura, cae al calendario tal cual (sin la regex ruidosa). Caché con TTL para no llamar al
modelo en cada carga del telar. Loombit DEBE acertar — nunca le pide al usuario que revise.
"""

from __future__ import annotations

import json
import re
import time
from datetime import date
from typing import Any

_DIAS_ES = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")

# Caché en proceso: clave (hash de entradas) → (timestamp, resultado). Evita llamar al LLM en cada
# carga del telar; el contexto del día no cambia cada segundo.
_CACHE: dict[int, tuple[float, list[dict]]] = {}
_TTL_SEGUNDOS = 600  # 10 min

_SYSTEM = (
    "Eres el destilador de reuniones de Loombit, un operador administrativo. Te doy los correos "
    "recientes del usuario y los eventos de su calendario. Devuelve SOLO un array JSON con las "
    "reuniones/citas FUTURAS reales del usuario, una entrada por reunión, con este formato exacto:\n"
    '[{"con":"<persona o empresa>","fecha":"YYYY-MM-DD","hora":"HH:MM","lugar":"<dirección o vacío>",'
    '"fuente":"correo|calendario","conflicto":true|false,"nota":"<si hay descuadre, explícalo>",'
    '"origen":"<asunto del correo o título del evento de donde lo sacas>"}]\n'
    "REGLAS INNEGOCIABLES:\n"
    "1) La VERDAD es lo que las personas ACUERDAN EXPLÍCITAMENTE en un correo (su palabra escrita). "
    'Si el calendario CONTRADICE ese acuerdo (otra fecha u hora), pon fuente="correo", '
    "conflicto=true y explica el descuadre en \"nota\" (p. ej. 'tu calendario la tiene el lunes 15').\n"
    "2) NO inventes NADA. Cada reunión DEBE salir de un correo o un evento concreto; cita el origen. "
    "Si un dato no aparece (p. ej. la hora o el lugar), déjalo en cadena vacía, no lo inventes.\n"
    "3) Solo reuniones de HOY en adelante. Ignora newsletters, recibos y avisos automáticos.\n"
    "4) Responde SOLO el array JSON, sin texto alrededor, sin markdown."
)


def _contexto_correos(correos: list[dict], maximo: int = 15) -> str:
    filas = []
    for c in correos[:maximo]:
        de = str(c.get("from", ""))[:60]
        asunto = str(c.get("subject", ""))[:80]
        snippet = str(c.get("snippet", ""))[:220]
        filas.append(f"- De: {de} | Asunto: {asunto} | {snippet}")
    return "\n".join(filas) if filas else "(sin correos recientes)"


def _contexto_eventos(eventos: list[dict]) -> str:
    filas = []
    for ev in eventos[:12]:
        inicio = str(ev.get("start", ""))[:16]
        lugar = str(ev.get("location", ""))
        filas.append(
            f"- {inicio} | {ev.get('summary', '(evento)')}" + (f" | {lugar}" if lugar else "")
        )
    return "\n".join(filas) if filas else "(calendario vacío)"


def _extraer_json(texto: str) -> Any:
    """Saca el array JSON aunque el modelo lo envuelva en ```json o añada texto."""
    t = texto.strip()
    t = re.sub(r"^```(?:json)?|```$", "", t, flags=re.MULTILINE).strip()
    ini, fin = t.find("["), t.rfind("]")
    if ini != -1 and fin != -1 and fin > ini:
        t = t[ini : fin + 1]
    return json.loads(t)


def _normalizar(item: dict, hoy: date) -> dict | None:
    """Valida y limpia una reunión del LLM. Descarta lo no anclado o las fechas pasadas/ inválidas."""
    fecha = str(item.get("fecha", "")).strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", fecha):
        return None
    try:
        d = date.fromisoformat(fecha)
    except ValueError:
        return None
    if d < hoy:  # una cita pasada no se propone
        return None
    hora = str(item.get("hora", "")).strip()
    if re.fullmatch(r"\d{3,4}", hora):  # "900"/"1057" → "9:00"/"10:57"
        hora = f"{hora[:-2]}:{hora[-2:]}"
    if hora and not re.fullmatch(r"\d{1,2}:\d{2}", hora):
        hora = ""
    if hora:  # cero-pad: "9:00" → "09:00"
        h, m = hora.split(":")
        hora = f"{int(h):02d}:{m}"
    con = str(item.get("con", "")).strip()
    origen = str(item.get("origen", "")).strip()
    if not con and not origen:  # sin ancla → no se afirma
        return None
    return {
        "con": con,
        "fecha": fecha,
        "hora": hora,
        "lugar": str(item.get("lugar", "")).strip(),
        "fuente": (
            "correo" if str(item.get("fuente", "")).lower().startswith("corr") else "calendario"
        ),
        "conflicto": bool(item.get("conflicto", False)),
        "nota": str(item.get("nota", "")).strip(),
        "origen": origen,
        "dia_semana": _DIAS_ES[d.weekday()],
    }


def _fallback_calendario(eventos: list[dict], hoy: date) -> list[dict]:
    """Sin LLM: el calendario tal cual (autoritativo, sin la regex ruidosa). No reconcilia, pero no
    inventa ni mete basura."""
    out = []
    for ev in eventos[:8]:
        inicio = str(ev.get("start", ""))
        fecha = inicio[:10]
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", fecha):
            continue
        try:
            d = date.fromisoformat(fecha)
        except ValueError:
            continue
        if d < hoy:
            continue
        out.append(
            {
                "con": str(ev.get("summary", "")).replace("Reunión con ", "").strip(),
                "fecha": fecha,
                "hora": inicio[11:16] if not ev.get("all_day") else "",
                "lugar": str(ev.get("location", "")).strip(),
                "fuente": "calendario",
                "conflicto": False,
                "nota": "",
                "origen": str(ev.get("summary", "")).strip(),
                "dia_semana": _DIAS_ES[d.weekday()],
            }
        )
    return out


_PREFIJOS_CITA = (
    "reunión con ",
    "reunion con ",
    "cita con ",
    "llamada con ",
    "videollamada con ",
    "reunión ",
    "reunion ",
)


def _contraparte(summary: str) -> str:
    """Saca el nombre del interlocutor del título de un evento ('Reunión con David' → 'David')."""
    s = (summary or "").strip()
    low = s.lower()
    for pref in _PREFIJOS_CITA:
        if low.startswith(pref):
            return s[len(pref) :].strip()
    return ""


def _recopilar_contexto(correos: list[dict], eventos: list[dict], buscar: Any) -> list[dict]:
    """Junta los correos relevantes para destilar: los recientes + (si hay buscador) una BÚSQUEDA en
    TODO el Gmail del interlocutor de cada reunión del calendario. Así el hilo donde se acordó la
    fecha real entra en contexto aunque sea más viejo que la bandeja reciente. Dedup por (de+asunto).
    """
    juntos = list(correos or [])
    if buscar:
        for nombre in list({_contraparte(ev.get("summary", "")) for ev in eventos if ev})[:4]:
            if not nombre:
                continue
            try:
                juntos.extend((buscar(nombre) or [])[:5])
            except Exception:
                continue
    vistos: set = set()
    fuera: list[dict] = []
    for c in juntos:
        clave = (str(c.get("from", ""))[:40], str(c.get("subject", ""))[:60])
        if clave in vistos:
            continue
        vistos.add(clave)
        fuera.append(c)
    return fuera[:20]


def _clave(correos: list[dict], eventos: list[dict], hoy: date) -> int:
    firma = (
        hoy.isoformat(),
        tuple(sorted(str(c.get("subject", "")) + str(c.get("snippet", ""))[:40] for c in correos)),
        tuple(sorted(str(e.get("start", "")) + str(e.get("summary", "")) for e in eventos)),
    )
    return hash(firma)


def destilar_reuniones(
    correos: list[dict],
    eventos: list[dict],
    hoy: date,
    llm: Any = None,
    buscar: Any = None,
    usar_cache: bool = True,
) -> list[dict]:
    """Reuniones reales del usuario, destiladas por el LLM y reconciliadas (correo manda sobre un
    calendario que lo contradiga). `buscar(nombre)->correos` busca al interlocutor de cada reunión en
    TODO el Gmail (más allá de la bandeja reciente). Cae al calendario si el LLM falla. Cacheado por TTL.
    """
    if not correos and not eventos:
        return []  # nada que destilar → no se molesta al modelo
    clave = _clave(correos, eventos, hoy)
    if usar_cache:
        hit = _CACHE.get(clave)
        if hit and (time.time() - hit[0]) < _TTL_SEGUNDOS:
            return hit[1]

    contexto = _recopilar_contexto(correos, eventos, buscar)
    resultado: list[dict]
    try:
        from .llm import LLMClient

        cliente = llm or LLMClient()
        user = (
            f"CORREOS (relevantes para tus reuniones):\n{_contexto_correos(contexto, maximo=20)}\n\n"
            f"CALENDARIO (próximos días):\n{_contexto_eventos(eventos)}\n\n"
            f"Hoy es {hoy.isoformat()} ({_DIAS_ES[hoy.weekday()]}). Devuelve el array JSON:"
        )
        raw = cliente.chat(
            [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": user}],
            temperature=0,
            max_tokens=600,
        ).content
        data = _extraer_json(raw)
        if not isinstance(data, list):
            raise ValueError("el LLM no devolvió un array")
        resultado = [m for m in (_normalizar(it, hoy) for it in data if isinstance(it, dict)) if m]
    except Exception:
        resultado = _fallback_calendario(eventos, hoy)

    resultado.sort(key=lambda m: (m["fecha"], m["hora"] or "99:99"))
    if usar_cache:
        _CACHE[clave] = (time.time(), resultado)
    return resultado
