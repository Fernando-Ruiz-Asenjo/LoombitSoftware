"""
routine_executors.py — ejecutores concretos para las Routines + armado por defecto.

El motor (`scheduler.py`) es neutro y recibe un executor inyectado. Aquí vive el
executor real basado en el LLM instructor (14B) y el armado del scheduler por defecto
(store seedeado con el Brief diario). Separado para evitar import circular con el router.
"""

from __future__ import annotations

from datetime import datetime

from .llm import LLMClient
from .routines import CronSchedule, Routine, RoutineStore, brief_diario_routine
from .scheduler import RoutineScheduler
from .skills import SkillSafetyClass

_BRIEF_SYSTEM = (
    "Eres Loombit, operador administrativo local. Responde SIEMPRE en español, en un "
    "brief de máximo 5 líneas, en lenguaje natural, sin JSON ni markdown."
)

_MEJORA_SYSTEM = (
    "Eres el ingeniero de mejora continua de Loombit. Te paso el estado de auto-chequeo "
    "(qué evals están verdes/rojos y qué huecos quedan sin eval). Devuelve, en español y "
    "conciso: (1) 2-3 PRÓXIMOS PASOS sólidos y concretos para cerrar los huecos, y (2) 2-3 "
    "TEMAS A INVESTIGAR en internet (métodos/papers/patrones) para avanzar con método, no por "
    "suerte. Sé específico y honesto; no inventes que algo está hecho."
)


def brief_executor(routine: Routine, now: datetime) -> str:
    """Compone el output de una rutina con el LLM instructor (rol por defecto = 14B).

    Honesto: aún no hay conectores de lectura (Gmail/Calendar/banco), así que el
    contexto es mínimo y se declara como tal; el brief crecerá cuando esas fuentes existan.
    """
    contexto = (
        "Aún no hay fuentes conectadas (Gmail/Calendar/banco). "
        "Genera un brief honesto de demostración con la estructura pedida; no inventes datos."
    )
    messages = [
        {"role": "system", "content": _BRIEF_SYSTEM},
        {"role": "user", "content": f"{routine.objective}\n\nContexto disponible: {contexto}"},
    ]
    return LLMClient().chat(messages, max_tokens=300).content.strip()


def mejora_continua_routine() -> Routine:
    """Routine de mejora continua: lunes 09:00. Codifica el 'proponer soluciones + investigar
    métodos' para que el sistema avance solo, sin que haya que pedírselo. PASSIVE (solo informa)."""
    return Routine(
        name="Mejora continua",
        schedule=CronSchedule("0 9 * * 1"),
        objective=(
            "Revisa el auto-chequeo y los huecos del eval-set; propón los próximos pasos sólidos "
            "y los temas a investigar en internet para seguir avanzando con método."
        ),
        safety=SkillSafetyClass.PASSIVE,
        output_kind="mejora",
    )


def mejora_continua_executor(routine: Routine, now: datetime) -> str:
    """Codifica el bucle de mejora: parte del estado REAL del sistema (auto-chequeo + huecos) y
    pide al LLM propuestas concretas + temas a investigar. La búsqueda web autónoma es el siguiente
    enganche (necesita una tool de búsqueda cableada a la routine); por ahora nombra los temas."""
    try:
        from .selfcheck import run_selfcheck

        chk = run_selfcheck()
        estado = (
            f"Auto-chequeo: {chk.get('verdes', 0)}/{chk.get('total', 0)} verdes. "
            f"Rojos: {chk.get('fallos') or 'ninguno'}. "
            f"Huecos sin eval: {chk.get('pendientes_sin_eval') or 'ninguno'}."
        )
    except Exception as exc:
        estado = f"(No se pudo leer el auto-chequeo: {exc!r})"

    messages = [
        {"role": "system", "content": _MEJORA_SYSTEM},
        {"role": "user", "content": f"{routine.objective}\n\nEstado actual:\n{estado}"},
    ]
    return LLMClient().chat(messages, max_tokens=400).content.strip()


_REPLY_SYSTEM = (
    "Eres Loombit y escribes COMO Fernando (primera persona), nunca como IA/bot. Te paso un "
    "correo que alguien le ha enviado a Fernando y el contexto de quién es. Devuelve SOLO un "
    "borrador de respuesta breve, natural y profesional en español, firmado por Fernando. "
    "Si el correo trata algo DELICADO o importante (dinero, plazos legales, decisiones, quejas), "
    "empieza la respuesta con la marca '[IMPORTANTE]' para que Fernando lo revise."
)


def _buscar_respuestas(token: str, contactos: list, dias: int = 2, maximo: int = 10) -> list[dict]:
    """Lee correos SIN LEER recientes de los contactos conocidos (read-only). Devuelve remitente,
    asunto y snippet. Es percepción: no envía nada."""
    import httpx

    emails = {c.email.lower(): c.name for c in contactos if getattr(c, "email", "")}
    if not emails:
        return []
    h = {"Authorization": f"Bearer {token}"}
    q = f"is:unread newer_than:{dias}d from:(" + " OR ".join(emails.keys()) + ")"
    out: list[dict] = []
    try:
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
    except Exception:
        return out
    return out


def reply_watch_executor(routine: Routine, now: datetime) -> str:
    """Vigila respuestas: detecta correos sin leer de contactos conocidos y prepara un borrador
    de respuesta para cada uno (no envía; el humano aprueba). Memoria persistente del contacto."""
    from types import SimpleNamespace

    from .agent.memory import get_memory
    from .config import get_settings
    from .routers.home import _contactos_de_gmail
    from .skill_blanca_oauth import fresh_access_token

    settings = get_settings()
    token = fresh_access_token(settings, "google")
    if not token:
        return "No puedo vigilar respuestas: Google no está conectado."

    # A quién vigilar = a quien REALMENTE escribes (Enviados) + memoria; excluye tu propio correo.
    mem = get_memory()
    propio = (mem.owner.get("email") or "").lower()
    por_email: dict[str, object] = {}
    for c in _contactos_de_gmail(settings):
        em = c["email"].lower()
        if em and em != propio:
            por_email[em] = SimpleNamespace(name=c["name"], email=c["email"])
    for c in mem.contacts:
        em = (getattr(c, "email", "") or "").lower()
        if em and em != propio:
            por_email.setdefault(em, c)
    contactos = list(por_email.values())
    respuestas = _buscar_respuestas(token, contactos)
    if not respuestas:
        return "Sin respuestas nuevas de tus contactos."

    llm = LLMClient()
    lineas: list[str] = []
    for rsp in respuestas:
        quien = rsp["from"]
        ctx = f"De: {quien}\nAsunto: {rsp['subject']}\nMensaje: {rsp['snippet']}"
        try:
            borrador = llm.chat(
                [
                    {"role": "system", "content": _REPLY_SYSTEM},
                    {"role": "user", "content": ctx},
                ],
                max_tokens=300,
            ).content.strip()
        except Exception as exc:
            borrador = f"(no pude redactar el borrador: {exc})"
        marca = "  ⚠ IMPORTANTE" if "[IMPORTANTE]" in borrador else ""
        lineas.append(
            f"• {quien} — «{rsp['subject']}»{marca}\n  Te dijo: {rsp['snippet'][:140]}\n  Borrador: {borrador}"
        )

    return f"Tienes {len(respuestas)} respuesta(s) de contactos:\n\n" + "\n\n".join(lineas)


def vigilar_respuestas_routine() -> Routine:
    """Routine proactiva: cada 15 min en horario laboral, mira si tus contactos te han respondido
    y prepara borradores. ASSISTED (el humano aprueba el envío con 'Aprobar todo')."""
    return Routine(
        name="Vigilar respuestas",
        schedule=CronSchedule("*/15 8-20 * * 1-5"),
        objective="Detecta respuestas nuevas de tus contactos y prepara el borrador de cada una.",
        safety=SkillSafetyClass.ASSISTED,
        output_kind="reply_watch",
        enabled=False,  # opt-in: se activa cuando el daemon proactivo esté en marcha
    )


def default_executor(routine: Routine, now: datetime) -> str:
    """Despacha al executor según el tipo de routine (un solo punto de entrada para el scheduler)."""
    if routine.output_kind == "mejora":
        return mejora_continua_executor(routine, now)
    if routine.output_kind == "reply_watch":
        return reply_watch_executor(routine, now)
    return brief_executor(routine, now)


def ensure_default_routines(store: RoutineStore) -> RoutineStore:
    """Siembra las routines por defecto si faltan (Brief diario + Mejora continua)."""
    nombres = {r.name for r in store.list()}
    if "Brief diario" not in nombres:
        store.add(brief_diario_routine())
    if "Mejora continua" not in nombres:
        store.add(mejora_continua_routine())
    if "Vigilar respuestas" not in nombres:
        store.add(vigilar_respuestas_routine())
    return store


def build_default_scheduler() -> RoutineScheduler:
    """Store seedeado + scheduler con el dispatcher de executors. Usado por el router y el daemon."""
    store = ensure_default_routines(RoutineStore())
    return RoutineScheduler(store, default_executor)
