"""
Herramientas base del agente — sin dependencias externas extra.

Las 7 tools que desbloquean autonomía real desde el primer día:

  read_file       — leer cualquier fichero del workspace
  write_file      — crear o sobreescribir un fichero
  list_directory  — listar contenido de una carpeta
  web_fetch       — obtener el contenido de una URL (httpx)
  run_shell       — ejecutar un comando de shell [requires_approval]
  task_done       — marcar la tarea como completada (para el loop)
  request_approval — pausar y pedir confirmación humana

Con estas 7 herramientas Loombit puede:
  - Leer y escribir ficheros (facturas, informes, datos)
  - Navegar la web (buscar información, verificar datos)
  - Ejecutar comandos (con aprobación del humano)
  - Reconocer cuándo ha terminado

Estado: 🟡 — implementadas, pendiente prueba en bucle real.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import httpx

from .registry import ToolDefinition, tool_registry

# Directorio raíz seguro para operaciones de fichero (configurable)
_WORKSPACE_ROOT = Path.cwd()

# ── Implementaciones ──────────────────────────────────────────────────────────


def _read_file(path: str, max_chars: int = 8000) -> str:
    p = Path(path).expanduser()
    if not p.exists():
        return f"ERROR: fichero no encontrado: {path}"
    if not p.is_file():
        return f"ERROR: la ruta no es un fichero: {path}"
    try:
        content = p.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"ERROR al leer {path}: {exc}"
    if len(content) > max_chars:
        content = content[:max_chars] + f"\n[... truncado a {max_chars} caracteres ...]"
    return content


def _write_file(path: str, content: str) -> str:
    p = Path(path).expanduser()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"OK: fichero guardado en {p} ({len(content)} caracteres)"
    except OSError as exc:
        return f"ERROR al escribir {path}: {exc}"


def _list_directory(path: str, pattern: str = "*") -> str:
    p = Path(path).expanduser()
    if not p.exists():
        return f"ERROR: directorio no encontrado: {path}"
    if not p.is_dir():
        return f"ERROR: la ruta no es un directorio: {path}"
    try:
        entries = sorted(p.glob(pattern))
    except Exception as exc:
        return f"ERROR al listar {path}: {exc}"
    if not entries:
        return f"Directorio vacío: {path}"
    lines = []
    for e in entries[:100]:
        kind = "DIR " if e.is_dir() else "FILE"
        size = f"{e.stat().st_size:>10,} B" if e.is_file() else "          -"
        lines.append(f"{kind}  {size}  {e.name}")
    result = "\n".join(lines)
    if len(entries) > 100:
        result += f"\n[... y {len(entries) - 100} entradas más ...]"
    return result


def _web_fetch(url: str, max_chars: int = 6000) -> str:
    try:
        with httpx.Client(timeout=15, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": "Loombit-Operator/0.1"})
        text = resp.text
        # Quitar etiquetas HTML básicas para ahorrar tokens
        import re

        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
        text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) > max_chars:
            text = text[:max_chars] + "\n[... truncado ...]"
        return f"URL: {url}\nHTTP: {resp.status_code}\n\n{text}"
    except Exception as exc:
        return f"ERROR al obtener {url}: {exc}"


def _run_shell(command: str, timeout: int = 30) -> str:
    """Ejecuta un comando de shell. SIEMPRE requiere aprobación humana."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        parts = [f"EXIT: {result.returncode}"]
        if stdout:
            parts.append(f"STDOUT:\n{stdout}")
        if stderr:
            parts.append(f"STDERR:\n{stderr}")
        return "\n".join(parts)
    except subprocess.TimeoutExpired:
        return f"ERROR: comando excedió timeout de {timeout}s"
    except Exception as exc:
        return f"ERROR al ejecutar comando: {exc}"


def _task_done(summary: str) -> str:
    """Señal especial — el loop la detecta y termina el ciclo."""
    return f"TASK_DONE:{summary}"


def _request_approval(reason: str, proposed_action: str) -> str:
    """Señal especial — el loop la detecta y pausa esperando confirmación."""
    payload = json.dumps({"reason": reason, "proposed_action": proposed_action}, ensure_ascii=False)
    return f"PENDING_APPROVAL:{payload}"


def _ask_user(question: str) -> str:
    """Hace una pregunta al usuario en el chat. El loop pausa y espera la respuesta."""
    payload = json.dumps({"question": question}, ensure_ascii=False)
    return f"PENDING_QUESTION:{payload}"


# ── Registrar en el registry global ──────────────────────────────────────────

tool_registry.register(
    ToolDefinition(
        name="read_file",
        description="Lee fichero local. Devuelve texto (max 8000 chars).",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
        fn=_read_file,
        category="file",
    )
)

tool_registry.register(
    ToolDefinition(
        name="write_file",
        description="Crea o sobreescribe un fichero. Crea directorios si no existen.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
        fn=_write_file,
        category="file",
    )
)

tool_registry.register(
    ToolDefinition(
        name="list_directory",
        description="Lista carpeta. pattern: glob como '*.pdf' (default '*').",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "pattern": {"type": "string", "default": "*"},
            },
            "required": ["path"],
        },
        fn=_list_directory,
        category="file",
    )
)

tool_registry.register(
    ToolDefinition(
        name="web_fetch",
        description="Obtiene contenido de URL. Devuelve texto limpio sin HTML.",
        parameters={
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
        fn=_web_fetch,
        category="web",
    )
)

tool_registry.register(
    ToolDefinition(
        name="run_shell",
        description="Ejecuta comando shell. Requiere aprobacion humana siempre.",
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "timeout": {"type": "integer", "default": 30},
            },
            "required": ["command"],
        },
        fn=_run_shell,
        requires_approval=True,
        safety_class="safety_sensitive",
        category="shell",
    )
)

tool_registry.register(
    ToolDefinition(
        name="task_done",
        description="Marca tarea completada. Llamar SIEMPRE al terminar con resumen del resultado.",
        parameters={
            "type": "object",
            "properties": {"summary": {"type": "string"}},
            "required": ["summary"],
        },
        fn=_task_done,
        category="base",
    )
)

tool_registry.register(
    ToolDefinition(
        name="request_approval",
        description="Pausa y pide aprobacion humana. Usar antes de enviar email, borrar ficheros, etc.",
        parameters={
            "type": "object",
            "properties": {
                "reason": {"type": "string"},
                "proposed_action": {"type": "string"},
            },
            "required": ["reason", "proposed_action"],
        },
        fn=_request_approval,
        requires_approval=True,
        safety_class="assisted",
        category="base",
    )
)

tool_registry.register(
    ToolDefinition(
        name="ask_user",
        description="Pregunta al usuario SOLO si falta un dato IMPOSIBLE de obtener con tools (p.ej. el email de un destinatario que no aparece en contactos, o una preferencia personal suya). NUNCA preguntes el asunto ni el cuerpo de un correo: esos los REDACTAS tú a partir del encargo.",
        parameters={
            "type": "object",
            "properties": {
                "question": {"type": "string"},
            },
            "required": ["question"],
        },
        fn=_ask_user,
        category="base",
    )
)


def _propose_improvement(issue: str, suggestion: str, category: str = "general") -> str:
    """
    El agente registra en memoria una carencia o mejora que ha detectado
    durante la ejecución de una tarea. No interrumpe el flujo.

    Categorías válidas: tool_missing | behavior | memory | ui | integration | general
    """
    try:
        from ..agent.memory import get_memory
        import inspect

        # Obtener el run_id del frame de llamada (best-effort)
        run_id = ""
        for frame_info in inspect.stack():
            local_run = frame_info.frame.f_locals.get("run")
            if local_run and hasattr(local_run, "id"):
                run_id = local_run.id
                break
        get_memory().add_proposal(
            issue=issue,
            suggestion=suggestion,
            category=category,
            run_id=run_id,
        )
        return json.dumps(
            {
                "ok": True,
                "message": f"Propuesta registrada: [{category}] {issue[:80]}",
            },
            ensure_ascii=False,
        )
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)


tool_registry.register(
    ToolDefinition(
        name="propose_improvement",
        description=(
            "Registra una carencia o mejora detectada durante la ejecucion de la tarea. "
            "Usar cuando el agente no puede completar algo por falta de una tool, "
            "comportamiento incorrecto, limitacion de memoria u otro problema. "
            "Categorias: tool_missing | behavior | memory | ui | integration | general."
        ),
        parameters={
            "type": "object",
            "properties": {
                "issue": {
                    "type": "string",
                    "description": "Descripcion concisa de la carencia o problema",
                },
                "suggestion": {
                    "type": "string",
                    "description": "Sugerencia de mejora o feature a implementar",
                },
                "category": {
                    "type": "string",
                    "enum": ["tool_missing", "behavior", "memory", "ui", "integration", "general"],
                    "default": "general",
                },
            },
            "required": ["issue", "suggestion"],
        },
        fn=_propose_improvement,
        category="base",
    )
)
