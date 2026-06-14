"""
sandbox/policy.py — K2: valla de AUTOPROTECCIÓN del sistema de ficheros.

El agente (Qwen) PROPONE tool-calls; `write_file`/`run_shell` ejecutan. Sin valla, `write_file`
(que AUTO-ejecuta, sin gate humano) puede sobreescribir el PROPIO código de LoomBit (`loop.py`,
`authority_plane.py`), el gate (`verify.py`, `.githooks/`), la constitución (`CLAUDE.md`,
`BRUJULA.md`), `.env` o el token store de OAuth — una escalada TOTAL (el agente reescribe sus
propios guardarraíles, la 2ª vía 🔴 del red team).

Esta valla DENIEGA por construcción cualquier escritura que caiga dentro del SISTEMA (código/gate/
constitución/git/CI/tests) o sobre CREDENCIALES. Determinista, fail-closed, sin red. Deny-por-defecto
sobre lo protegido; lo demás (documentos del usuario en `runtime/`, su carpeta, etc.) se permite.

Frontera honesta: cubre escritura por RUTA (`write_file`) y los patrones de escritura más comunes en
`run_shell` (redirecciones y verbos `rm/cp/mv/sed -i/tee/dd/chmod`). NO es un sandbox de proceso (eso
es K11); un comando shell ofuscado podría sortearla — por eso `run_shell` SIGUE siendo `requires_approval`
(el humano ve y aprueba el comando). Aquí se cierra el agujero ANCHO (write_file auto-ejecutable).
"""

from __future__ import annotations

import re
from pathlib import Path

# Raíz del repo: .../loombit_operator/sandbox/policy.py → parents[2].
_REPO = Path(__file__).resolve().parents[2]

# Directorios del SISTEMA que el agente NUNCA puede escribir (su código, el gate, git, CI, tests).
_DIRS_PROTEGIDOS = (
    _REPO / "loombit_operator",
    _REPO / "scripts",
    _REPO / "tests",
    _REPO / ".githooks",
    _REPO / ".git",
    _REPO / ".github",
)
# Ficheros sueltos protegidos: constitución + config del gate.
_FICHEROS_PROTEGIDOS = (
    _REPO / "CLAUDE.md",
    _REPO / "pyproject.toml",
    _REPO / "docs" / "BRUJULA.md",
)


def _dentro_de(p: Path, base: Path) -> bool:
    try:
        p.relative_to(base)
        return True
    except ValueError:
        return False


def ruta_protegida(path: str) -> tuple[bool, str]:
    """¿`path` cae sobre algo que el agente NO puede escribir? Devuelve (protegida, motivo).
    Resuelve la ruta (normaliza `..` y symlinks) para que no se sortee con path-traversal."""
    try:
        p = Path(path).expanduser().resolve()
    except (OSError, RuntimeError, ValueError):
        return True, "ruta no resoluble (fail-closed)"
    nombre = p.name.lower()
    # Credenciales: cualquier .env y el token store de OAuth (esté donde esté, incl. runtime/).
    if nombre == ".env" or nombre.startswith(".env."):
        return True, "fichero de credenciales (.env)"
    if "skill_blanca_oauth_token" in nombre or nombre.endswith("_tokens.json"):
        return True, "token store de OAuth (credenciales)"
    for base in _DIRS_PROTEGIDOS:
        if _dentro_de(p, base):
            return (
                True,
                f"dentro de «{base.name}/» — el agente no reescribe el código/gate de LoomBit",
            )
    for f in _FICHEROS_PROTEGIDOS:
        if p == f:
            return True, f"fichero de gobierno/config protegido ({f.name})"
    return False, ""


_MSG_VALLA = (
    "🛡️ BLOQUEADO (autoprotección): no escribo en «{path}» — {motivo}. El agente no toca su propio "
    "código, el gate, la constitución ni las credenciales. Guarda los documentos en una ruta del "
    "usuario (p. ej. dentro de runtime/local/ o tu carpeta), no en el sistema."
)


def verificar_escritura(path: str) -> str | None:
    """None si la escritura es segura; el mensaje de bloqueo si la ruta está protegida (write_file)."""
    protegida, motivo = ruta_protegida(path)
    return _MSG_VALLA.format(path=path, motivo=motivo) if protegida else None


# ── run_shell: deny de los patrones de ESCRITURA más comunes sobre rutas protegidas ───────────────
_VERBOS_ESCRITURA = re.compile(
    r">>?|\btee\b|\bsed\s+-i\b|\bcp\b|\bmv\b|\bdd\b|\bchmod\b|\bchown\b|\brm\b|\btruncate\b|\bln\b"
)
_TOKENS_PROTEGIDOS = (
    "loombit_operator/",
    "loombit_operator\\",
    "scripts/",
    ".githooks",
    ".github",
    ".git/",
    ".env",
    "_tokens.json",
    "skill_blanca_oauth_token",
    "claude.md",
    "brujula.md",
    "pyproject.toml",
)


def comando_peligroso(command: str) -> tuple[bool, str]:
    """¿El comando shell parece ESCRIBIR/MODIFICAR una ruta protegida? Conservador (fail-safe): si
    menciona una ruta del sistema Y trae un verbo de escritura, se deniega. Defensa en profundidad —
    `run_shell` además ES `requires_approval`. Lecturas/ejecuciones (`python -m …`, `cat`, `grep`) pasan.
    """
    c = (command or "").lower()
    if not any(t in c for t in _TOKENS_PROTEGIDOS):
        return False, ""
    if _VERBOS_ESCRITURA.search(c):
        return True, "el comando escribe/modifica una ruta del sistema (código/gate/credenciales)"
    return False, ""
