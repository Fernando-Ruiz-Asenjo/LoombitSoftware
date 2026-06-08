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


# ── F7 — saltos de línea literales del modelo ───────────────────────────────────
def _f7_normaliza_saltos() -> tuple[bool, str]:
    out = normalize_email_text("Hola Jana,\\n\\nMensaje.\\n\\nUn saludo")
    ok = "\\n" not in out and "\n\n" in out
    return ok, "saltos normalizados" if ok else f"sigue literal: {out[:40]!r}"


CASES: list[Eval] = [
    Eval("F1.subject", "F1", "No preguntar el asunto del correo", _f1_no_pregunta_asunto),
    Eval("F2.no_invent", "F2", "Bloquear destinatario inventado", _f2_bloquea_email_inventado),
    Eval(
        "F2.user_email", "F2", "Permitir email dado por el usuario", _f2_permite_email_del_usuario
    ),
    Eval(
        "F2.resolved", "F2", "Permitir email de contacts_find", _f2_permite_email_de_contacts_find
    ),
    Eval(
        "F5.provenance",
        "F5",
        "Marcar auto-capturado como no fiable",
        _f5_procedencia_auto_vs_google,
    ),
    Eval("F7.newlines", "F7", "Normalizar saltos literales", _f7_normaliza_saltos),
    # Huecos conocidos (aún sin eval automatizado — honestidad del proceso vivo):
    Eval("F3.single_source", "F3", "Resolución de contacto única y rankeada", None),
    Eval("F4.no_bot", "F4", "No presentarse como bot (juez de calidad)", None, needs_llm=True),
    Eval("F6.reflexion", "F6", "Aprender del fallo (Reflexion) en vez de repetir", None),
    Eval("F8.run_hygiene", "F8", "Ciclo de vida de runs sin huérfanos", None),
]
