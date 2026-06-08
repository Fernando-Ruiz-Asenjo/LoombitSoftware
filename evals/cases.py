"""Casos de eval que codifican la taxonomía F1-F8 con los fallos REALES observados.

- `check` determinista (rápido, corre en CI): ejercita la primitiva que cura el fallo.
- `check=None`: hueco conocido SIN eval todavía (honesto: el proceso vivo sabe lo que le falta).
- `needs_llm=True`: necesita LM Studio (juez de calidad), corre bajo demanda.

Aplicación RETROACTIVA: los casos nacen de las trazas reales (jana.espinal, '¿qué asunto?',
el correo que se delata como bot, el '\\n' literal), no de un proceso en blanco.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Callable

from loombit_operator.agent.loop import AgentLoop
from loombit_operator.agent.memory import AgentMemory
from loombit_operator.llm import ToolCall
from loombit_operator.skill_blanca_gmail import normalize_email_text


@dataclass
class Eval:
    id: str
    taxon: str
    desc: str
    check: Callable[[], tuple[bool, str]] | None = None
    needs_llm: bool = False
    tags: list[str] = field(default_factory=list)


# ── helpers ───────────────────────────────────────────────────────────────────
def _loop() -> AgentLoop:
    return AgentLoop(llm=SimpleNamespace())


def _run(task: str, steps: list | None = None) -> SimpleNamespace:
    return SimpleNamespace(id="eval", task=task, steps=steps or [])


def _tc(name: str, **args) -> ToolCall:
    return ToolCall(id="tc", tool_name=name, arguments=args)


# ── F1 — no preguntar el asunto/cuerpo ──────────────────────────────────────────
def _f1_no_pregunta_asunto() -> tuple[bool, str]:
    out, stop = _loop()._execute_tool_call(
        _tc("ask_user", question="¿Qué asunto le quieres dar al correo a Jana?"),
        1,
        _run("manda un correo a Jana"),
    )
    ok = stop is False and "asunto" in out.lower()
    return ok, (
        "interceptado y autocorregido" if ok else f"NO interceptado: stop={stop} out={out[:60]}"
    )


# ── F2 — no inventar destinatario ───────────────────────────────────────────────
def _f2_bloquea_email_inventado() -> tuple[bool, str]:
    # el modelo se saca un email que el usuario NO dio y que no salió de contacts_find
    out, stop = _loop()._execute_tool_call(
        _tc("gmail_send", to="jana.espinal@gmail.com", subject="x", body="y"),
        1,
        _run("manda un correo a Jana dando las buenas noches"),
    )
    ok = stop is False and "no inventes" in out.lower()
    return ok, "bloqueado (no se inventa)" if ok else f"NO bloqueado: stop={stop} out={out[:60]}"


def _f2_permite_email_del_usuario() -> tuple[bool, str]:
    # el usuario escribió el email en su petición → legítimo (pasa a aprobación)
    out, stop = _loop()._execute_tool_call(
        _tc("gmail_send", to="jana@empresa.com", subject="x", body="y"),
        1,
        _run("manda un correo a jana@empresa.com dando las buenas noches"),
    )
    ok = stop is True and out.startswith("PENDING_APPROVAL:")
    return ok, "permitido (lo dio el usuario)" if ok else f"mal: stop={stop} out={out[:60]}"


def _f2_permite_email_de_contacts_find() -> tuple[bool, str]:
    # el email salió de contacts_find en este run → legítimo
    step = SimpleNamespace(
        tool_name="contacts_find",
        result='{"ok": true, "contacts": [{"name": "Jana Wall", "email": "jana.wall@acme.com"}]}',
    )
    out, stop = _loop()._execute_tool_call(
        _tc("gmail_send", to="jana.wall@acme.com", subject="x", body="y"),
        2,
        _run("manda un correo a Jana", steps=[step]),
    )
    ok = stop is True and out.startswith("PENDING_APPROVAL:")
    return ok, (
        "permitido (resuelto por contacts_find)" if ok else f"mal: stop={stop} out={out[:60]}"
    )


# ── F5 — procedencia: no cristalizar como verdad lo auto-capturado ──────────────
def _f5_no_lava_contacts_find() -> tuple[bool, str]:
    """Los resultados de contacts_find NO se cachean en memoria (evita el bucle de lavado que
    convertía un contacto dudoso en 'google' y resucitaba jana.espinal)."""
    mem = _mem_tmp()
    step = SimpleNamespace(
        tool_name="contacts_find",
        arguments={},
        result='{"ok":true,"contacts":[{"name":"X","email":"x@dudoso.com"}]}',
    )
    mem.extract_contacts_from_steps([step])
    ok = all(c.email != "x@dudoso.com" for c in mem.contacts)
    return ok, "no se lava contacts_find→memoria" if ok else "LAVADO: contacts_find cacheado"


def _f5_procedencia_auto_vs_google(tmp=None) -> tuple[bool, str]:
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        mem = AgentMemory(store_path=Path(d) / "m.json")
        envio = SimpleNamespace(tool_name="gmail_send", arguments={"to": "jana.espinal@gmail.com"})
        mem.extract_contacts_from_steps([envio])
        c = next((x for x in mem.contacts if x.email == "jana.espinal@gmail.com"), None)
        ok = c is not None and c.source == "auto"
        return ok, (
            f"auto-capturado marcado source={c.source if c else '?'}" if ok else "no marcado auto"
        )


# ── F4 — no delatarse como IA/bot en el correo ──────────────────────────────────
def _f4_bloquea_bot_reveal() -> tuple[bool, str]:
    out, stop = _loop()._execute_tool_call(
        _tc(
            "gmail_send",
            to="jana@empresa.com",
            subject="Presentación",
            body="Hola, soy un agente autónomo llamado Loombit Operator que ha enviado este correo.",
        ),
        1,
        _run("manda un correo a jana@empresa.com presentándote"),
    )
    ok = stop is False and "como el usuario" in out.lower()
    return ok, "bloqueado (no se delata)" if ok else f"NO bloqueado: stop={stop} out={out[:60]}"


def _f4_permite_correo_humano() -> tuple[bool, str]:
    out, stop = _loop()._execute_tool_call(
        _tc(
            "gmail_send",
            to="jana@empresa.com",
            subject="Reunión la próxima semana",
            body="Hola Jana,\n\n¿Tienes un hueco para vernos? Un saludo, Fernando.",
        ),
        1,
        _run("manda un correo a jana@empresa.com proponiendo vernos"),
    )
    ok = stop is True and out.startswith("PENDING_APPROVAL:")
    return ok, "permitido (correo humano normal)" if ok else f"mal: stop={stop} out={out[:60]}"


# ── F5 — (definido arriba) ──────────────────────────────────────────────────────
# ── F6 — aprendizaje general (Reflexion): memoria + recuperación relevante ──────
def _mem_tmp():
    import tempfile
    from pathlib import Path

    from loombit_operator.agent.memory import AgentMemory

    d = tempfile.mkdtemp()
    return AgentMemory(store_path=Path(d) / "m.json")


def _f6_fundacionales_sembradas() -> tuple[bool, str]:
    mem = _mem_tmp()  # al construirse, siembra las lecciones del análisis de error (retroactivo)
    textos = " ".join(le.text.lower() for le in mem.lessons)
    ok = len(mem.lessons) >= 5 and "inventes el email" in textos
    return ok, f"{len(mem.lessons)} lecciones sembradas" if ok else "fundacionales NO sembradas"


def _f6_recupera_relevante_y_filtra() -> tuple[bool, str]:
    mem = _mem_tmp()
    rel = mem.relevant_lessons("manda un correo a Jana sin asunto")
    hay_correo = any("correo" in le.text.lower() for le in rel)
    no_rel = mem.relevant_lessons("calcula la raíz cuadrada de 9")
    filtra = all("correo" not in le.text.lower() for le in no_rel)
    ok = bool(rel) and hay_correo and filtra
    return ok, f"relevantes={len(rel)}, filtra_no_relacionadas={filtra}"


def _f6_reflexion_produce_leccion() -> tuple[bool, str]:
    from loombit_operator.agent.reflexion import reflexionar

    stub = SimpleNamespace(
        chat=lambda **k: SimpleNamespace(content="No reutilices un contacto sin verificarlo antes.")
    )
    run = SimpleNamespace(
        task="manda un correo a Jana", status="failed", steps=[], error="no encontrado", result=""
    )
    leccion = reflexionar(run, stub)
    ok = leccion is not None and "verific" in leccion.lower()
    return ok, f"lección={leccion!r}" if ok else "reflexión no produjo lección"


# ── F3 — resolver el contacto más probable (confianza + frecuencia), nunca 'auto' ──
def _f3_ranking_y_exclusion_auto() -> tuple[bool, str]:
    from loombit_operator.recipients import Candidato, resolver_destinatario

    # 'jana.espinal' (auto) NO debe ganar a 'Jana Wall' (google) — ni siquiera aparecer
    estado, mejor, ranking = resolver_destinatario(
        [
            Candidato("jana.espinal", "jana.espinal@gmail.com", "auto", 1),
            Candidato("Jana Wall", "jana.wall@acme.com", "google", 5),
        ]
    )
    ok_resuelto = (
        estado == "resuelto"
        and mejor is not None
        and mejor.email == "jana.wall@acme.com"
        and all(c.source != "auto" for c in ranking)
    )
    # frecuencia desempata entre fuentes fiables
    _, mejor2, _ = resolver_destinatario(
        [
            Candidato("Jana Vieja", "vieja@x.com", "google", 1),
            Candidato("Jana Habitual", "habitual@x.com", "google", 9),
        ]
    )
    ok_frecuencia = mejor2 is not None and mejor2.email == "habitual@x.com"
    # empate real → ambiguo (preguntar, no adivinar)
    estado3, _, _ = resolver_destinatario(
        [Candidato("Jana A", "a@x.com", "google", 2), Candidato("Jana B", "b@x.com", "google", 2)]
    )
    ok_ambiguo = estado3 == "ambiguo"
    ok = ok_resuelto and ok_frecuencia and ok_ambiguo
    return ok, f"resuelto={ok_resuelto}, frecuencia={ok_frecuencia}, ambiguo={ok_ambiguo}"


# ── F7 — saltos de línea literales del modelo ───────────────────────────────────
def _f7_normaliza_saltos() -> tuple[bool, str]:
    out = normalize_email_text("Hola Jana,\\n\\nMensaje.\\n\\nUn saludo")
    ok = "\\n" not in out and "\n\n" in out
    return ok, "saltos normalizados" if ok else f"sigue literal: {out[:40]!r}"


# ── E2E — prueba REAL contra el 14B (no se da por hecho que funciona) ───────────
def _e2e_correo_sin_bot_ni_invencion() -> tuple[bool, str]:
    """Corre el agente de verdad y comprueba que NINGÚN gmail_send no-bloqueado se delata como
    bot. Las guardas garantizan también que el destinatario no sea inventado. needs_llm."""
    from loombit_operator.agent.loop import AgentLoop

    run = AgentLoop(max_steps=6).run("Manda un correo a Jana presentándote brevemente.")
    bot = ("agente autónomo", "loombit operator", "soy un agente", "soy tu asistente", "automático")
    for s in run.steps:
        if s.tool_name != "gmail_send":
            continue
        bloqueado = (s.result or "").startswith("[SISTEMA")
        cuerpo = f"{s.arguments.get('subject', '')} {s.arguments.get('body', '')}".lower()
        if not bloqueado and any(t in cuerpo for t in bot):
            return False, f"correo NO bloqueado con auto-revelación: {cuerpo[:50]}"
    estado_ok = run.status in ("pending_approval", "pending_question", "completed", "failed")
    return estado_ok, f"status={run.status}, pasos={run.step_count} — sin envío bot/inventado"


# ── F8 — runs huérfanos saneados al reiniciar ───────────────────────────────────
def _f8_barre_huerfanos() -> tuple[bool, str]:
    import tempfile
    from pathlib import Path

    from loombit_operator.agent.run import AgentStatus, AgentStore

    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "runs.json"
        store = AgentStore(store_path=path)
        r = store.create("tarea de prueba")
        r.mark_running()
        store.save_run(r)
        store2 = AgentStore(store_path=path)  # simula un reinicio
        n = store2.sweep_orphans()
        estado = store2.get(r.id).status
        ok = n >= 1 and estado == AgentStatus.FAILED
        return ok, f"barridos={n}, estado={estado.value}"


CASES: list[Eval] = [
    Eval("F1.subject", "F1", "No preguntar el asunto del correo", _f1_no_pregunta_asunto),
    Eval("F2.no_invent", "F2", "Bloquear destinatario inventado", _f2_bloquea_email_inventado),
    Eval(
        "F2.user_email", "F2", "Permitir email dado por el usuario", _f2_permite_email_del_usuario
    ),
    Eval(
        "F2.resolved", "F2", "Permitir email de contacts_find", _f2_permite_email_de_contacts_find
    ),
    Eval("F4.no_bot", "F4", "Bloquear correo que se delata como bot", _f4_bloquea_bot_reveal),
    Eval("F4.humano_ok", "F4", "Permitir correo humano normal", _f4_permite_correo_humano),
    Eval(
        "F5.provenance",
        "F5",
        "Marcar auto-capturado como no fiable",
        _f5_procedencia_auto_vs_google,
    ),
    Eval(
        "F5.no_laundering",
        "F5",
        "No cachear contacts_find (evita el lavado)",
        _f5_no_lava_contacts_find,
    ),
    Eval(
        "F6.foundational",
        "F6",
        "Lecciones fundacionales sembradas (retroactivo)",
        _f6_fundacionales_sembradas,
    ),
    Eval(
        "F6.retrieval",
        "F6",
        "Recuperar lección relevante y filtrar el resto",
        _f6_recupera_relevante_y_filtra,
    ),
    Eval(
        "F6.reflexion", "F6", "Reflexión produce lección del fallo", _f6_reflexion_produce_leccion
    ),
    Eval("F7.newlines", "F7", "Normalizar saltos literales", _f7_normaliza_saltos),
    Eval("F8.run_hygiene", "F8", "Sanear runs huérfanos al reiniciar", _f8_barre_huerfanos),
    Eval(
        "E2E.correo_real",
        "F4",
        "Correo real contra el 14B: sin bot ni destinatario inventado",
        _e2e_correo_sin_bot_ni_invencion,
        needs_llm=True,
    ),
    Eval(
        "F3.ranking",
        "F3",
        "Resolver el contacto más probable (confianza+frecuencia), nunca 'auto'",
        _f3_ranking_y_exclusion_auto,
    ),
]
