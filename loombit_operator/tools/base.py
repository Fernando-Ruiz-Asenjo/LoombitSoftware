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
from typing import Any

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
    payload = json.dumps({"reason": reason, "proposed_action": proposed_action})
    return f"PENDING_APPROVAL:{payload}"


# ── Registrar en el registry global ──────────────────────────────────────────

tool_registry.register(ToolDefinition(
    name="read_file",
    description=(
        "Lee el contenido de un fichero del sistema de archivos local. "
        "Útil para leer facturas, contratos, informes, configuraciones, código, etc. "
        "Devuelve el texto del fichero (máx. 8000 caracteres)."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Ruta absoluta o relativa al fichero a leer.",
            },
        },
        "required": ["path"],
    },
    fn=_read_file,
    category="file",
))

tool_registry.register(ToolDefinition(
    name="write_file",
    description=(
        "Crea o sobreescribe un fichero con el contenido dado. "
        "Crea los directorios intermedios si no existen. "
        "Úsalo para guardar informes, borradores, datos procesados, etc."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Ruta del fichero a crear/sobreescribir.",
            },
            "content": {
                "type": "string",
                "description": "Contenido a escribir en el fichero.",
            },
        },
        "required": ["path", "content"],
    },
    fn=_write_file,
    category="file",
))

tool_registry.register(ToolDefinition(
    name="list_directory",
    description=(
        "Lista los ficheros y subdirectorios de una carpeta. "
        "Acepta patrones glob (ej. '*.pdf', '*.xlsx'). "
        "Útil para explorar dónde están los documentos."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Ruta del directorio a listar.",
            },
            "pattern": {
                "type": "string",
                "description": "Patrón glob para filtrar (por defecto '*' = todo).",
                "default": "*",
            },
        },
        "required": ["path"],
    },
    fn=_list_directory,
    category="file",
))

tool_registry.register(ToolDefinition(
    name="web_fetch",
    description=(
        "Obtiene el contenido de una URL (página web, API JSON, etc.). "
        "Devuelve el texto limpio de la página (sin HTML). "
        "Úsalo para buscar información, verificar datos, consultar APIs públicas."
    ),
    parameters={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "URL completa a obtener (https://...).",
            },
        },
        "required": ["url"],
    },
    fn=_web_fetch,
    category="web",
))

tool_registry.register(ToolDefinition(
    name="run_shell",
    description=(
        "Ejecuta un comando de shell en el sistema operativo. "
        "IMPORTANTE: esta tool siempre requiere aprobación humana antes de ejecutarse. "
        "Úsala cuando ninguna otra tool cubra la necesidad."
    ),
    parameters={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Comando shell a ejecutar.",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout en segundos (por defecto 30).",
                "default": 30,
            },
        },
        "required": ["command"],
    },
    fn=_run_shell,
    requires_approval=True,
    safety_class="safety_sensitive",
    category="shell",
))

tool_registry.register(ToolDefinition(
    name="task_done",
    description=(
        "Marca la tarea como completada. Llama a esta tool cuando hayas terminado "
        "todo el trabajo y tengas un resultado o resumen para el usuario. "
        "El parámetro 'summary' debe describir qué hiciste y qué resultado obtuviste."
    ),
    parameters={
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "Resumen de lo que se hizo y el resultado obtenido.",
            },
        },
        "required": ["summary"],
    },
    fn=_task_done,
    category="base",
))

tool_registry.register(ToolDefinition(
    name="request_approval",
    description=(
        "Pausa la ejecución y solicita aprobación humana antes de continuar. "
        "Úsala cuando vayas a realizar una acción irreversible o de alto impacto "
        "(enviar un email real, borrar ficheros, hacer pagos, etc.)."
    ),
    parameters={
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "description": "Por qué necesitas aprobación.",
            },
            "proposed_action": {
                "type": "string",
                "description": "Descripción exacta de lo que harás si se aprueba.",
            },
        },
        "required": ["reason", "proposed_action"],
    },
    fn=_request_approval,
    requires_approval=True,
    safety_class="assisted",
    category="base",
))
