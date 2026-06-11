"""
routine_executors.py — ejecutores concretos para las Routines + armado por defecto.

El motor (`scheduler.py`) es neutro y recibe un executor inyectado. Aquí vive el
executor real basado en el LLM instructor (14B) y el armado del scheduler por defecto
(store seedeado con el Brief diario). Separado para evitar import circular con el router.
"""

from __future__ import annotations

import re
from datetime import datetime

from .llm import LLMClient
from .routines import CronSchedule, Routine, RoutineStore, brief_diario_routine
from .scheduler import RoutineScheduler
from .skills import SkillSafetyClass

_BRIEF_SYSTEM = (
    "Eres Loombit, operador administrativo local. Responde SIEMPRE en español, en un brief de "
    "máximo 4 líneas, natural, sin JSON ni markdown. Usa SOLO los datos reales que te paso: "
    "NO inventes vencimientos, plazos, cifras ni tareas. Si no hay nada, dilo en una línea."
)

_MEJORA_SYSTEM = (
    "Eres el ingeniero de mejora continua de Loombit. Te paso el estado de auto-chequeo "
    "(qué evals están verdes/rojos y qué huecos quedan sin eval). Devuelve, en español y "
    "conciso: (1) 2-3 PRÓXIMOS PASOS sólidos y concretos para cerrar los huecos, y (2) 2-3 "
    "TEMAS A INVESTIGAR en internet (métodos/papers/patrones) para avanzar con método, no por "
    "suerte. Sé específico y honesto; no inventes que algo está hecho."
)


def _señales_reales(now: datetime | None = None) -> list[str]:
    """Señales REALES de hoy para el brief: agenda de hoy + respuestas sin leer de contactos
    + aprobaciones pendientes + cuentas a cobrar. Sin inventar nada; si una fuente falla,
    simplemente no aporta señal."""
    señales: list[str] = []
    try:
        from .skill_blanca_calendar_read import eventos_de_hoy

        eventos = eventos_de_hoy(now=now)
        if eventos:
            titulos = "; ".join(e.get("summary", "") for e in eventos[:5])
            señales.append(f"{len(eventos)} evento(s) hoy en tu agenda: {titulos}")
        else:
            señales.append("sin eventos en tu calendario hoy")
    except Exception:
        pass
    # Asuntos COMPRENDIDOS de la bandeja (Skill D · Comprensión): se leen de la caché que el motor
    # calcula en segundo plano (reuniones reconciliadas, notificaciones oficiales, plazos), con su
    # estado. El brief NO llama al LLM aquí — lee lo ya comprendido. Si la caché está vacía, no aporta.
    try:
        from .comprension import comprension_cacheada

        for a in comprension_cacheada()[0][:5]:
            cuando = ""
            if a.get("fecha"):
                from datetime import date as _date

                d = _date.fromisoformat(a["fecha"])
                cuando = " " + ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")[d.weekday()]
                cuando += f" {d.day}/{d.month}" + (f" {a['hora']}" if a.get("hora") else "")
            estado = f" ({a['estado'].replace('_', ' ')})" if a.get("estado") else ""
            señales.append(f"{a.get('titulo', 'asunto')}{cuando}{estado}".strip())
    except Exception:
        pass
    try:
        from types import SimpleNamespace

        from .agent.memory import get_memory
        from .config import get_settings
        from .routers.home import _contactos_de_gmail
        from .skill_blanca_oauth import fresh_access_token

        settings = get_settings()
        token = fresh_access_token(settings, "google")
        if token:
            propio = (get_memory().owner.get("email") or "").lower()
            contactos = [
                SimpleNamespace(name=c["name"], email=c["email"])
                for c in _contactos_de_gmail(settings)
                if c["email"].lower() != propio
            ]
            n = len(_buscar_respuestas(token, contactos))
            señales.append(
                f"{n} correo(s) sin leer de tus contactos"
                if n
                else "ningún correo sin leer de contactos"
            )
    except Exception:
        pass
    # Percepción AMPLIA: cuántos correos recientes hay en la bandeja (de cualquiera, no solo
    # contactos). Las reuniones ya las destila el bloque de arriba. Best-effort.
    try:
        from .telar import _fuente_inbox

        inbox = _fuente_inbox(None, incluir_leidos=True)
        if inbox:
            señales.append(f"{len(inbox)} correo(s) reciente(s) en tu bandeja")
    except Exception:
        pass
    try:
        from .agent import AgentStatus
        from .agent.run import AgentStore

        pend = AgentStore().list(status=AgentStatus.PENDING_APPROVAL)
        if pend:
            señales.append(f"{len(pend)} aprobación(es) pendiente(s)")
    except Exception:
        pass
    try:
        from .cuentas_cobrar import CuentasCobrarStore

        cc = CuentasCobrarStore()
        venc = cc.vencidas()
        prox = cc.proximas(7)
        if venc:
            total = sum(c.importe for c in venc)
            señales.append(f"{len(venc)} cuenta(s) a cobrar VENCIDA(s) por {total:.0f} €")
        if prox:
            señales.append(f"{len(prox)} cuenta(s) a cobrar vencen en 7 días")
    except Exception:
        pass
    return señales


def brief_executor(routine: Routine, now: datetime) -> str:
    """Brief HONESTO a partir de datos REALES de hoy (no inventa). El LLM solo redacta."""
    señales = _señales_reales()
    contexto = "; ".join(señales) if señales else "sin señales conectadas hoy"
    messages = [
        {"role": "system", "content": _BRIEF_SYSTEM},
        {
            "role": "user",
            "content": f"{routine.objective}\n\nDATOS REALES DE HOY (no añadas nada más): {contexto}.",
        },
    ]
    return LLMClient().chat(messages, max_tokens=250).content.strip()


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


def _email_de(header: str) -> str:
    m = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", header or "")
    return m.group(0) if m else ""


# Correos que NO piden respuesta: acuses/confirmaciones (incl. respuestas de Calendar) y automáticos.
# Cognición honesta: una confirmación no necesita otra confirmación (no proponer responder a algo
# ya cerrado). Conservador: ante la duda, sí pide respuesta.
_NO_RESPUESTA_ASUNTO = re.compile(
    r"^\s*(re:\s*|fwd:\s*|rv:\s*)*(aceptad|accepted|rechazad|declined|provisional|tentative|"
    r"invitaci[óo]n aceptada|invitation accepted|confirmaci[óo]n de)",
    re.IGNORECASE,
)
_NO_RESPUESTA_BLOB = re.compile(
    r"\b(no-?reply|noreply|no responder|do not reply|respuesta autom[áa]tica|automatic reply|"
    r"out of office|fuera de (la )?oficina|de vacaciones|mensaje autom[áa]tico|newsletter|"
    r"bolet[íi]n|unsubscribe|darse de baja|ha aceptado la invitaci[óo]n|se ha aceptado la invitaci[óo]n)\b",
    re.IGNORECASE,
)


def _necesita_respuesta(subject: str, snippet: str = "") -> bool:
    """¿Este correo PIDE una respuesta? Excluye acuses/confirmaciones y automáticos."""
    s = subject or ""
    if _NO_RESPUESTA_ASUNTO.search(s):
        return False
    return not _NO_RESPUESTA_BLOB.search(f"{s} {snippet or ''}")


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
                subject = hdrs.get("Subject", "")
                snippet = data.get("snippet", "")[:300]
                # Una confirmación/acuse ya cerrado no pide respuesta → no lo propongas (cognición).
                if not _necesita_respuesta(subject, snippet):
                    continue
                out.append(
                    {
                        "id": m["id"],
                        "from": hdrs.get("From", ""),
                        "subject": subject,
                        "snippet": snippet,
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

    # Dedup: no volver a preparar un borrador del mismo correo cada minuto.
    import json as _json

    seen_path = settings.routine_receipt_dir.parent / "replied_ids.json"
    try:
        seen = set(_json.loads(seen_path.read_text(encoding="utf-8")))
    except Exception:
        seen = set()

    # Crea un run PROACTIVO por cada respuesta nueva: redacta y se queda en pending_approval
    # (nunca auto-envía) → aparece en "Aprobar todo" para que el humano lo mande de un clic.
    from .routers.agent import _get_loop

    loop = _get_loop()
    nuevas = 0
    for rsp in respuestas:
        if rsp["id"] in seen:
            continue
        dest = _email_de(rsp["from"])
        if not dest:
            continue
        task = (
            f"Responde al correo que te ha enviado {rsp['from']} (asunto: «{rsp['subject']}»). "
            f"Su mensaje: «{rsp['snippet']}». Redacta una respuesta breve y natural EN MI NOMBRE "
            f"(en primera persona, firmando con mi nombre de la memoria; sin decir que eres IA) "
            f"y envíala con gmail_send a {dest} "
            f"con asunto «RE: {rsp['subject']}»."
        )
        try:
            run = loop.create(task=task, profile="administrativo")
            run.proactive = True
            loop.store.save_run(run)
            loop.execute_run(run.id)  # redacta + gmail_send → pending_approval
            nuevas += 1
        except Exception:
            pass
        seen.add(rsp["id"])

    try:
        seen_path.write_text(_json.dumps(sorted(seen)), encoding="utf-8")
    except Exception:
        pass

    if nuevas:
        return (
            f"Detecté {nuevas} respuesta(s) nueva(s) y preparé el borrador. "
            "Pendiente de tu aprobación en «Aprobar todo»."
        )
    return "Respuestas ya gestionadas (sin borradores nuevos)."


def vigilar_respuestas_routine() -> Routine:
    """Routine proactiva: cada 15 min en horario laboral, mira si tus contactos te han respondido
    y prepara borradores. ASSISTED (el humano aprueba el envío con 'Aprobar todo')."""
    return Routine(
        name="Vigilar respuestas",
        schedule=CronSchedule("* * * * *"),  # cada minuto: flujo rápido y efectivo
        objective="Detecta respuestas nuevas de tus contactos y prepara el borrador de cada una.",
        safety=SkillSafetyClass.ASSISTED,
        output_kind="reply_watch",
        enabled=True,
    )


def fabrica_skills_routine() -> Routine:
    """Routine de la Fábrica de Skills (Skill X): en 2º plano detecta huecos útiles, redacta y valida
    una tool con el coder local y PROPONE con gate. Nunca aplica. OPT-IN (enabled=False)."""
    return Routine(
        name="Fábrica de Skills",
        schedule=CronSchedule("0 4 * * *", tz="Europe/Madrid"),
        objective=(
            "Detecta huecos útiles (tools que el agente pidió o que fallan), redacta y valida una "
            "tool nueva con el arnés grado-foso y propónla para aprobación. No apliques nada."
        ),
        safety=SkillSafetyClass.SAFETY_SENSITIVE,
        output_kind="fabrica",
        enabled=False,
    )


def fabrica_skills_executor(routine: Routine, now: datetime) -> str:
    """Corre un ciclo de la Fábrica CONSULTANDO el Playbook (ACE, aprende en 2º plano) y añade un
    parte de salud del código (interno, sin LLM). No aplica nada; todo espera el gate humano."""
    try:
        from .fabrica.ciclo import ejecutar_ciclo
        from .fabrica.playbook import Playbook

        try:
            pb = Playbook()
        except Exception:  # noqa: BLE001 — sin playbook se corre igual
            pb = None
        informe = ejecutar_ciclo(max_necesidades=3, max_intentos=2, playbook=pb)
    except Exception as exc:  # noqa: BLE001
        return f"Fábrica: no pude correr el ciclo: {exc!r}"

    try:
        from .fabrica.mantenimiento import escanear_salud

        salud = escanear_salud()
    except Exception:  # noqa: BLE001 — la salud es best-effort; el ciclo manda
        salud = ""

    nuevas = informe.get("tools", {}).get("propuestas_pendientes_nuevas", [])
    hallazgos = informe.get("hallazgos_red_meta", {}).get("nuevos", 0)
    partes = []
    if nuevas:
        partes.append(f"{len(nuevas)} propuesta(s) de tool para aprobar (/fabrica/propuestas)")
    if hallazgos:
        partes.append(
            f"{hallazgos} hallazgo(s) de la Red/meta para revisar (/fabrica/oportunidades)"
        )
    if partes:
        base = "Fábrica: " + " · ".join(partes) + "."
    else:
        n = informe.get("oportunidades_detectadas", 0)
        base = f"Fábrica: {n} oportunidad(es) analizada(s); sin novedad que aprobar/revisar."
    return base + (f"\n{salud}" if salud else "")


def aprendizaje_routine() -> Routine:
    """Routine de aprendizaje proactivo (cierra Fase 5): de madrugada consolida la memoria —
    reindexa el índice semántico (RAG) y destila lecciones generales de los runs recientes. PASSIVE
    (solo lee/escribe en memoria e índice LOCALES; ningún efecto externo). Enabled, opt-in vía daemon.
    """
    return Routine(
        name="Aprendizaje",
        schedule=CronSchedule("30 4 * * *", tz="Europe/Madrid"),
        objective=(
            "Consolida la memoria: mantén fresco el índice semántico del histórico y destila "
            "lecciones generales de las últimas ejecuciones, para recordar mejor por significado."
        ),
        safety=SkillSafetyClass.PASSIVE,
        output_kind="aprendizaje",
        enabled=True,
    )


def aprendizaje_executor(routine: Routine, now: datetime) -> str:
    """Consolida la memoria (reindexa el RAG + Reflexion proactiva de los runs recientes)."""
    from .aprendizaje import consolidar

    return consolidar().get("resumen", "Aprendizaje: sin resultado.")


def decisiones_cobro_routine() -> Routine:
    """LD-3 «Loombit Decide»: en background, mira los cobros vencidos y ENCOLA una decisión por cada
    uno (el humano decide desde la cola). PASSIVE: solo encola decisiones LOCALES — ningún efecto
    externo (el envío sigue exigiendo al humano + el gate). Enabled, opt-in vía daemon."""
    return Routine(
        name="Decisiones de cobro",
        schedule=CronSchedule("0 8 * * 1-5", tz="Europe/Madrid"),
        objective=(
            "Revisa los cobros vencidos y prepara una decisión por cada uno en la cola, para que solo "
            "tengas que decidir; nada se envía sin tu aprobación."
        ),
        safety=SkillSafetyClass.PASSIVE,
        output_kind="decisiones",
        enabled=True,
    )


def decisiones_cobro_executor(routine: Routine, now: datetime) -> str:
    """Genera y encola decisiones de cobro al nivel de autonomía configurado. NUNCA actúa sola
    (§14B): solo sube decisiones a la cola; el efecto externo sigue siendo del humano + el gate."""
    from .autonomy import generar_decisiones_cobro, parse_level
    from .config import get_settings
    from .cuentas_cobrar import CuentasCobrarStore
    from .decisions import DecisionStore

    level = parse_level(get_settings().decide_autonomy_level)
    try:
        vencidas = CuentasCobrarStore().vencidas()
    except Exception:
        vencidas = []
    r = generar_decisiones_cobro(DecisionStore(), vencidas, today=now.date(), level=level)
    if r["nivel"] == "observa":
        return (
            f"Observadas {r['observadas']} decisión(es) de cobro (no encoladas: nivel «observa»)."
        )
    if r["encoladas"]:
        return f"Encoladas {r['encoladas']} decisión(es) de cobro (de {r['observadas']} vista(s))."
    return f"Sin decisiones nuevas de cobro (vistas {r['observadas']}; ya estaban en la cola)."


def default_executor(routine: Routine, now: datetime) -> str:
    """Despacha al executor según el tipo de routine (un solo punto de entrada para el scheduler)."""
    if routine.output_kind == "mejora":
        return mejora_continua_executor(routine, now)
    if routine.output_kind == "reply_watch":
        return reply_watch_executor(routine, now)
    if routine.output_kind == "fabrica":
        return fabrica_skills_executor(routine, now)
    if routine.output_kind == "aprendizaje":
        return aprendizaje_executor(routine, now)
    if routine.output_kind == "decisiones":
        return decisiones_cobro_executor(routine, now)
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
    if "Fábrica de Skills" not in nombres:
        store.add(fabrica_skills_routine())
    if "Aprendizaje" not in nombres:
        store.add(aprendizaje_routine())
    if "Decisiones de cobro" not in nombres:
        store.add(decisiones_cobro_routine())
    return store


def build_default_scheduler() -> RoutineScheduler:
    """Store seedeado + scheduler con el dispatcher de executors. Usado por el router y el daemon."""
    store = ensure_default_routines(RoutineStore())
    return RoutineScheduler(store, default_executor)
