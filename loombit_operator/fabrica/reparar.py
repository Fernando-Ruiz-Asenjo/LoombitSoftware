"""
reparar.py — propone una MEJORA del código en uso como diff VALIDADO, con gate. Nunca auto-aplica.

Modificar código que ya está programado y funcionando es lo más sensible: aquí el gate es sagrado.
El coder propone una versión mejorada del fichero (un arreglo de bug, un troceo, un prompt mejor);
se valida ESTÁTICAMENTE (parse + black + ruff con la config del repo) y se devuelve un DIFF unificado
como PROPUESTA. No se escribe nada: la validación de comportamiento (tests) ocurre cuando un humano
aplica el diff en una rama (donde corre el pre-commit gate). Vale igual para código y para prompts.
"""

from __future__ import annotations

import ast
import difflib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

_IGNORAR = shutil.ignore_patterns(
    ".git",
    "__pycache__",
    "*.pyc",
    "runtime",
    ".venv",
    "venv",
    "node_modules",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "build",
    "dist",
    "*.egg-info",
)

_SISTEMA = (
    "Eres ingeniero de Loombit (núcleo blanco). Te doy el contenido COMPLETO de un fichero del "
    "proyecto y una instrucción de mejora. Devuelve SOLO el contenido COMPLETO del fichero ya "
    "mejorado (mismo módulo, listo para sustituirlo), sin explicaciones ni fences. Respeta el "
    "estilo (black, líneas ≤ 99), no cambies la API pública salvo que la instrucción lo pida, y "
    "mantén los comentarios/docstrings en español."
)
_TIMEOUT = 30


def _validar_contenido(contenido: str, nombre: str) -> tuple[bool, dict[str, str], str]:
    """Valida y NORMALIZA el fichero propuesto: black lo formatea (el coder aporta la lógica) y ruff
    (config del repo) lo aprueba. Devuelve (ok, detalle, contenido_normalizado)."""
    try:
        import black

        normalizado = black.format_str(contenido, mode=black.Mode())  # parsea + formatea
    except Exception as exc:  # noqa: BLE001 — no compila o black no pudo: rechazo limpio
        return False, {"parse_black": f"no compila/formatea: {exc}"}, contenido

    detalle = {"parse": "OK", "black": "OK"}
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "ruff", "check", "--stdin-filename", nombre, "-"],
            input=normalizado,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=_TIMEOUT,
        )
        if proc.returncode != 0:
            return (
                False,
                {**detalle, "ruff": (proc.stdout or proc.stderr or "").strip()[:200]},
                normalizado,
            )
        detalle["ruff"] = "OK"
    except FileNotFoundError:
        detalle["ruff"] = "ruff no ejecutable (omitido)"
    return True, detalle, normalizado


def _simbolos_publicos(src: str) -> set[str]:
    """Nombres públicos de nivel superior (funciones/clases/constantes sin `_`). Sirve para que un
    parche NO pueda borrar la API en uso: el fallo clásico del modelo (devolver medio fichero) que la
    validación de estilo NO detecta. Solo AST, no ejecuta nada."""
    try:
        arbol = ast.parse(src)
    except SyntaxError:
        return set()
    nombres: set[str] = set()
    for nodo in arbol.body:
        if isinstance(nodo, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            if not nodo.name.startswith("_"):
                nombres.add(nodo.name)
        elif isinstance(nodo, ast.Assign):
            for t in nodo.targets:
                if isinstance(t, ast.Name) and not t.id.startswith("_"):
                    nombres.add(t.id)
    return nombres


def _pedir_mejora(
    original: str, instruccion: str, nombre: str, llm: Any, reglas: str = ""
) -> str | None:
    extra = f"\n{reglas}\n" if reglas else ""
    msgs = [
        {"role": "system", "content": _SISTEMA},
        {
            "role": "user",
            "content": f"FICHERO: {nombre}\nINSTRUCCIÓN: {instruccion}{extra}"
            f"\n\n--- CONTENIDO ACTUAL ---\n{original}",
        },
    ]
    try:
        resp = llm.chat(messages=msgs, temperature=0.1, max_tokens=4000)
        texto = (getattr(resp, "content", "") or "").strip()
    except Exception:  # noqa: BLE001
        return None
    # Quita fences ```python ... ``` si el modelo los puso.
    if texto.startswith("```"):
        texto = texto.split("\n", 1)[-1]
        if texto.rstrip().endswith("```"):
            texto = texto.rstrip()[:-3]
    return texto or None


def _raiz_repo() -> Path:
    return Path(__file__).resolve().parents[2]


def validar_comportamiento(
    archivo_rel: str,
    contenido: str,
    raiz_repo: Path | None = None,
    pytest_args: list[str] | None = None,
    timeout: int = 240,
) -> tuple[bool, str]:
    """Segundo cinturón: copia el repo a un dir AISLADO, aplica el parche y corre los tests. El árbol
    vivo NO se toca. Es la verdad de tierra para reparar código en uso (lo que el guard estático no ve).
    Devuelve (tests_verdes, detalle)."""
    raiz_repo = raiz_repo or _raiz_repo()
    tmp = Path(tempfile.mkdtemp(prefix="fabrica_check_"))
    destino = tmp / "repo"
    try:
        shutil.copytree(raiz_repo, destino, ignore=_IGNORAR)
        objetivo = destino / archivo_rel
        if not objetivo.exists():
            return False, f"no existe {archivo_rel} en la copia"
        objetivo.write_text(contenido, encoding="utf-8")
        cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--no-cov"]
        cmd += pytest_args or []
        proc = subprocess.run(
            cmd, cwd=destino, capture_output=True, text=True, encoding="utf-8", timeout=timeout
        )
        ok = proc.returncode == 0
        cola = [ln for ln in (proc.stdout or "").strip().splitlines() if ln.strip()]
        return ok, ("tests verdes" if ok else "tests ROJOS: " + (cola[-1] if cola else "fallo"))
    except Exception as exc:  # noqa: BLE001
        return False, f"no se pudo validar comportamiento: {exc!r}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def proponer_parche(
    archivo: str | Path,
    instruccion: str,
    llm: Any = None,
    raiz: Path | None = None,
    validar_tests: bool = False,
    playbook: Any = None,
) -> dict[str, Any] | None:
    """Propone una mejora del fichero `archivo` como diff validado. Devuelve {archivo, instruccion,
    diff, validacion, ok} o None si el coder no produce algo usable. NUNCA escribe el fichero.
    Si se pasa `playbook`, inyecta sus reglas de reparación más relevantes en el prompt."""
    ruta = Path(raiz, archivo) if raiz else Path(archivo)
    try:
        original = ruta.read_text(encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"no se pudo leer {ruta}: {exc}"}

    if llm is None:
        try:
            from ..llm import LLMClient

            llm = LLMClient(role="coder")
        except Exception:  # noqa: BLE001
            return None

    reglas = ""
    if playbook is not None:
        try:
            reglas = playbook.como_contexto(f"reparar {ruta.name} {instruccion}")
        except Exception:  # noqa: BLE001
            reglas = ""
    propuesto = _pedir_mejora(original, instruccion, ruta.name, llm, reglas)
    if not propuesto or propuesto.strip() == original.strip():
        return None

    ok, validacion, normalizado = _validar_contenido(propuesto, ruta.name)
    # Guard de API en uso: el parche NO puede eliminar símbolos públicos (no romper lo que funciona).
    faltan = _simbolos_publicos(original) - _simbolos_publicos(normalizado)
    if faltan:
        ok = False
        validacion["api"] = f"elimina símbolos públicos EN USO: {', '.join(sorted(faltan))}"
    final = normalizado if normalizado.endswith("\n") else normalizado + "\n"

    # Segundo cinturón (opt-in): correr los tests contra el parche en un repo aislado.
    if ok and validar_tests:
        tests_ok, detalle_tests = validar_comportamiento(str(archivo), final)
        validacion["comportamiento"] = detalle_tests
        ok = ok and tests_ok
    diff = "".join(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            final.splitlines(keepends=True),
            fromfile=f"a/{ruta.name}",
            tofile=f"b/{ruta.name}",
        )
    )
    return {
        "ok": ok,
        "archivo": str(archivo),
        "instruccion": instruccion,
        "validacion": validacion,
        "diff": diff,
        "nota": "PROPUESTA — revísala y aplícala en una rama (allí corren los tests). No se ha escrito nada.",
    }
