"""
comprension.py — COGNICIÓN de la bandeja (Skill D · Comprensión).

No es extraer un dato suelto: es COMPRENDER cada hilo importante — quién escribe, de qué va la
conversación, en qué estado está (¿confirmado por ambos?, ¿pendiente de respuesta?, ¿requiere una
gestión?), y qué debería hacer el usuario. De esa comprensión derivan las cosas: una reunión cerrada,
una notificación oficial que requiere acción, un plazo. La verdad es lo que las personas dicen
EXPLÍCITAMENTE en el correo; si el calendario lo contradice, manda el correo.

FIABILIDAD (regla de Fernando: NO PUEDE HABER FALLOS): el LLM es lento y a veces falla. Por eso esto
NO se llama en caliente desde el telar. Se calcula en SEGUNDO PLANO y se PERSISTE; el telar lee
siempre el último resultado bueno. Si el modelo falla, se conserva el último bueno — NUNCA se cae al
calendario crudo (que es justo lo que daba el dato equivocado). Si aún no hay nada, el telar muestra
"verificando…", nunca un dato sin verificar.
"""

from __future__ import annotations

import json
import re
import threading
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .config import get_settings

_DIAS_ES = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
_TTL_REFRESCO = 600  # s: si la caché es más vieja, se relanza un refresco en segundo plano
_lock = threading.Lock()
_refrescando = False

_SYSTEM = (
    "Eres el cerebro de comprensión de la bandeja de Loombit, un operador administrativo para un "
    "autónomo español. NO extraigas datos sueltos: COMPRENDE cada asunto importante leyendo los "
    "correos como una conversación — quién escribe, de qué va, en qué ESTADO está y qué debería hacer "
    "el usuario. Devuelve SOLO un array JSON; una entrada por asunto IMPORTANTE (ignora newsletters, "
    "promociones y avisos automáticos sin acción). Formato exacto de cada entrada:\n"
    '{"tipo":"reunion|notificacion|plazo|gestion","titulo":"<frase corta y clara>",'
    '"con":"<persona o entidad>","resumen":"<qué pasa y el contexto, en 1 frase>",'
    '"estado":"<confirmada|pendiente|requiere_accion|informativa>","fecha":"YYYY-MM-DD o vacío",'
    '"hora":"HH:MM o vacío","lugar":"<dirección o vacío>","importancia":1|2|3,'
    '"accion":"<qué debería hacer el usuario, o vacío>","origen":"<asunto del correo/evento>"}\n'
    "REGLAS INNEGOCIABLES:\n"
    "1) La VERDAD es lo que las personas ACUERDAN EXPLÍCITAMENTE en el correo (su palabra). Para una "
    "reunión, si en el hilo ambos confirman una fecha/hora/lugar, estado=confirmada y usa ESOS datos "
    "aunque el calendario diga otra cosa. Comprende el hilo completo (propuesta → confirmación).\n"
    "2) NO inventes NADA. Cada asunto sale de correos/eventos concretos; cita el origen. Dato que no "
    "aparece → cadena vacía.\n"
    "3) Lo oficial/legal (Policía, DGT, AEAT, Seguridad Social, banco, juzgado) es SIEMPRE importante "
    "(importancia 3) aunque no tenga fecha: tipo=notificacion, di qué pide y la acción.\n"
    "4) Solo cosas vigentes (de hoy en adelante o sin fecha). importancia: 3=urgente/legal, 2=normal, "
    "1=menor. Responde SOLO el array JSON, sin texto ni markdown."
)


def _cache_path() -> Path:
    base = Path(get_settings().agent_run_store_path).parent
    return base / "comprension_bandeja.json"


def comprension_cacheada() -> tuple[list[dict], float]:
    """(asuntos, edad_en_segundos). edad=inf si no hay caché todavía. Lectura instantánea, sin LLM."""
    p = _cache_path()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        edad = time.time() - float(data.get("ts", 0))
        return list(data.get("asuntos", [])), edad
    except Exception:
        return [], float("inf")


def _guardar(asuntos: list[dict]) -> None:
    p = _cache_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(
        json.dumps({"ts": time.time(), "asuntos": asuntos}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp.replace(p)


# ── Parsing / normalización ─────────────────────────────────────────────────────


def _extraer_json(texto: str) -> Any:
    t = re.sub(r"^```(?:json)?|```$", "", texto.strip(), flags=re.MULTILINE).strip()
    ini, fin = t.find("["), t.rfind("]")
    if ini != -1 and fin != -1 and fin > ini:
        t = t[ini : fin + 1]
    return json.loads(t)


_TIPOS = {"reunion", "notificacion", "plazo", "gestion"}
_ESTADOS = {"confirmada", "pendiente", "requiere_accion", "informativa"}


def _normalizar(item: dict, hoy: date) -> dict | None:
    titulo = str(item.get("titulo", "")).strip()
    origen = str(item.get("origen", "")).strip()
    if not titulo and not origen:
        return None  # sin ancla → no se afirma
    fecha = str(item.get("fecha", "")).strip()
    if fecha and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", fecha):
        fecha = ""
    if fecha:
        try:
            if date.fromisoformat(fecha) < hoy:  # cosa pasada con fecha → fuera
                return None
        except ValueError:
            fecha = ""
    hora = str(item.get("hora", "")).strip()
    if re.fullmatch(r"\d{3,4}", hora):
        hora = f"{hora[:-2]}:{hora[-2:]}"
    if hora and not re.fullmatch(r"\d{1,2}:\d{2}", hora):
        hora = ""
    if hora:
        h, m = hora.split(":")
        hora = f"{int(h):02d}:{m}"
    tipo = str(item.get("tipo", "")).strip().lower()
    estado = str(item.get("estado", "")).strip().lower()
    try:
        imp = int(item.get("importancia", 2))
    except (ValueError, TypeError):
        imp = 2
    return {
        "tipo": tipo if tipo in _TIPOS else "gestion",
        "titulo": titulo or origen,
        "con": str(item.get("con", "")).strip(),
        "resumen": str(item.get("resumen", "")).strip(),
        "estado": estado if estado in _ESTADOS else "",
        "fecha": fecha,
        "hora": hora,
        "lugar": str(item.get("lugar", "")).strip(),
        "importancia": min(3, max(1, imp)),
        "accion": str(item.get("accion", "")).strip(),
        "origen": origen,
        "dia_semana": _DIAS_ES[date.fromisoformat(fecha).weekday()] if fecha else "",
    }


# ── Recopilación de contexto (comprender exige CONTEXTO, no un correo suelto) ────


def _contexto(correos: list[dict], maximo: int = 22) -> str:
    filas = []
    for c in correos[:maximo]:
        de = str(c.get("from", ""))[:60]
        asunto = str(c.get("subject", ""))[:90]
        cuerpo = str(c.get("snippet", ""))[:240]
        filas.append(f"- De: {de} | Asunto: {asunto} | {cuerpo}")
    return "\n".join(filas) if filas else "(sin correos)"


def _eventos_txt(eventos: list[dict]) -> str:
    filas = []
    for ev in eventos[:12]:
        inicio = str(ev.get("start", ""))[:16]
        lugar = str(ev.get("location", ""))
        filas.append(
            f"- {inicio} | {ev.get('summary', '(evento)')}" + (f" | {lugar}" if lugar else "")
        )
    return "\n".join(filas) if filas else "(calendario vacío)"


_PREFIJOS_CITA = (
    "reunión con ",
    "reunion con ",
    "cita con ",
    "llamada con ",
    "reunión ",
    "reunion ",
)


def _contraparte(summary: str) -> str:
    s, low = (summary or "").strip(), (summary or "").strip().lower()
    for pref in _PREFIJOS_CITA:
        if low.startswith(pref):
            return s[len(pref) :].strip()
    return ""


def _recopilar(correos: list[dict], eventos: list[dict], buscar: Any) -> list[dict]:
    """Correos recientes + (si hay buscador) los hilos de cada interlocutor del calendario buscados en
    TODO el Gmail. Así el hilo donde se acordó/confirmó algo entra en contexto aunque sea más viejo.
    """
    juntos = list(correos or [])
    if buscar:
        for nombre in list({_contraparte(ev.get("summary", "")) for ev in (eventos or []) if ev})[
            :4
        ]:
            if nombre:
                try:
                    juntos.extend((buscar(nombre) or [])[:5])
                except Exception:
                    continue
    vistos, fuera = set(), []
    for c in juntos:
        k = (str(c.get("from", ""))[:40], str(c.get("subject", ""))[:60])
        if k not in vistos:
            vistos.add(k)
            fuera.append(c)
    return fuera[:22]


# ── Cómputo (segundo plano) ─────────────────────────────────────────────────────


def comprender(
    correos: list[dict], eventos: list[dict], hoy: date, llm: Any = None, buscar: Any = None
) -> list[dict] | None:
    """Una pasada de COMPRENSIÓN de la bandeja. Devuelve los asuntos entendidos, o None si el LLM
    falla (para conservar el último resultado bueno; NUNCA se cae al calendario crudo)."""
    if not correos and not eventos:
        return []
    contexto = _recopilar(correos, eventos, buscar)
    try:
        from .llm import LLMClient

        cliente = llm or LLMClient()
        user = (
            f"CORREOS (con su contexto):\n{_contexto(contexto)}\n\n"
            f"CALENDARIO (próximos días):\n{_eventos_txt(eventos)}\n\n"
            f"Hoy es {hoy.isoformat()} ({_DIAS_ES[hoy.weekday()]}). Comprende la bandeja. Array JSON:"
        )
        raw = cliente.chat(
            [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": user}],
            temperature=0,
            max_tokens=900,
        ).content
        data = _extraer_json(raw)
        if not isinstance(data, list):
            return None
        out = [a for a in (_normalizar(it, hoy) for it in data if isinstance(it, dict)) if a]
        out.sort(key=lambda a: (-a["importancia"], a["fecha"] or "9999", a["hora"] or "99:99"))
        return out
    except Exception:
        return None  # conservar el último bueno


def refrescar(
    correos: list[dict], eventos: list[dict], hoy: date, buscar: Any = None, llm: Any = None
) -> list[dict]:
    """Computa y PERSISTE si sale bien; si el LLM falla, conserva (devuelve) lo último cacheado."""
    nuevo = comprender(correos, eventos, hoy, llm=llm, buscar=buscar)
    if nuevo is not None:
        _guardar(nuevo)
        return nuevo
    return comprension_cacheada()[0]


def refrescar_async(
    correos: list[dict], eventos: list[dict], hoy: date, buscar: Any = None
) -> None:
    """Lanza un refresco en segundo plano (un solo refresco a la vez). El telar nunca espera al LLM."""
    global _refrescando
    with _lock:
        if _refrescando:
            return
        _refrescando = True

    def _run():
        global _refrescando
        try:
            refrescar(correos, eventos, hoy, buscar=buscar)
        finally:
            with _lock:
                _refrescando = False

    threading.Thread(target=_run, daemon=True).start()


def calentar_al_arrancar() -> None:
    """Calienta la caché al arrancar el server (best-effort, en segundo plano). Reúne sus fuentes."""

    def _run():
        try:
            from .skill_blanca_calendar_read import eventos_proximos
            from .telar import _buscar_correos, _fuente_inbox

            inbox = _fuente_inbox(None, incluir_leidos=True)
            prox = eventos_proximos(dias=7)
            refrescar(inbox, prox, datetime.now().date(), buscar=_buscar_correos)
        except Exception:
            pass

    threading.Thread(target=_run, daemon=True).start()
