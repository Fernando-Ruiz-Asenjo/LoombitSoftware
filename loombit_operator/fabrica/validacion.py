"""
validacion.py — el arnés grado-foso que valida una tool auto-escrita (la recompensa verificable).

Toda la automejora del estado del arte (DGM, AlphaEvolve, SICA, AZR) depende de un evaluador
automático con verdad de tierra. Aquí está el nuestro: una tool propuesta no se considera
buena hasta pasar, EN ORDEN, todas las puertas:

  1. seguridad   — gate AST (no os/subprocess/eval/dunders…); si falla, NO se ejecuta nada.
  2. contrato    — define la función con el nombre del contrato y un JSON-schema válido.
  3. formato     — `black` lo deja igual (estilo del repo).
  4. lint        — `ruff` sin quejas.
  5. importa     — compila e importa en un namespace aislado; la función es invocable.
  6. eval        — su propio check determinista pasa (una tool ÚTIL trae su prueba; sin eval
                   no es una tool, es una chorrada → puerta en rojo).
  7. sin_regresion — el eval-set existente (`selfcheck`) sigue verde (anti-overfit: lo nuevo
                   no rompe lo que ya funcionaba).

Devuelve un `Veredicto` con cada puerta. Solo si TODAS están verdes la propuesta es proponible.
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
import tempfile

from .modelos import BorradorTool, Veredicto
from .seguridad import analizar_seguridad, construir_namespace_seguro

_NOMBRE_TOOL = re.compile(r"[a-z][a-z0-9_]{2,40}")
_TIMEOUT = 30


def validar(borrador: BorradorTool) -> Veredicto:
    """Corre el arnés completo sobre el borrador y devuelve el veredicto (fail-fast)."""
    v = Veredicto()

    # 1. SEGURIDAD — sin esto no se ejecuta ni importa nada.
    seg = analizar_seguridad(borrador.source)
    v.añadir("seguridad", seg.ok, "código seguro" if seg.ok else "; ".join(seg.violaciones))
    if not seg.ok:
        return v
    if borrador.eval_source:
        seg_eval = analizar_seguridad(borrador.eval_source)
        if not seg_eval.ok:
            v.añadir("seguridad_eval", False, "; ".join(seg_eval.violaciones))
            return v

    # 2. CONTRATO — nombre válido, JSON-schema y la función existe en el source.
    ok_contrato, det_contrato = _check_contrato(borrador)
    v.añadir("contrato", ok_contrato, det_contrato)
    if not ok_contrato:
        return v

    # 3. FORMATO — NORMALIZA y adopta la versión black + ruff --fix. El modelo local aporta la
    #    LÓGICA; el validador garantiza el estilo (y así un 7B no se rechaza por espaciado).
    norm, det_norm = _normalizar(borrador.source)
    v.añadir("formato", norm is not None, det_norm)
    if norm is None:
        return v
    borrador.source = norm
    if not analizar_seguridad(norm).ok:  # re-veto sobre el código ya normalizado (defensa)
        v.puertas["seguridad"] = {"ok": False, "detalle": "el código normalizado no pasa seguridad"}
        return v

    # 4. LINT — confirma que tras el autofix no queda nada que ruff reproche.
    ok_lint, det_lint = _check_ruff(borrador.source)
    v.añadir("lint", ok_lint, det_lint)
    if not ok_lint:
        return v

    # 5. IMPORTA — exec en namespace aislado (ya vetado por seguridad) → función invocable.
    fn, det_imp = _importar(borrador)
    v.añadir("importa", fn is not None, det_imp)
    if fn is None:
        return v

    # 6. EVAL — su propio check determinista (sin eval → no es una tool útil).
    ok_eval, det_eval = _correr_eval(borrador, fn)
    v.añadir("eval", ok_eval, det_eval)
    if not ok_eval:
        return v

    # 7. SIN REGRESIÓN — el eval-set existente sigue verde.
    ok_reg, det_reg = _check_sin_regresion()
    v.añadir("sin_regresion", ok_reg, det_reg)
    return v


# ── Puertas individuales ────────────────────────────────────────────────────────


def _check_contrato(borrador: BorradorTool) -> tuple[bool, str]:
    if not _NOMBRE_TOOL.fullmatch(borrador.nombre):
        return False, f"nombre de tool inválido: '{borrador.nombre}' (snake_case, 3-40)"
    if not (borrador.descripcion or "").strip():
        return False, "falta descripción (el LLM la lee para decidir cuándo usar la tool)"
    p = borrador.parametros
    if (
        not isinstance(p, dict)
        or p.get("type") != "object"
        or not isinstance(p.get("properties"), dict)
    ):
        return False, "JSON-schema inválido (type=object + properties)"
    try:
        arbol = ast.parse(borrador.source)
    except SyntaxError as exc:
        return False, f"no compila: {exc.msg}"
    funcs = {n.name for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef)}
    if borrador.nombre not in funcs:
        return False, f"el source no define la función '{borrador.nombre}'"
    return True, f"contrato OK ({len(p['properties'])} parámetros)"


def _normalizar(source: str) -> tuple[str | None, str]:
    """Devuelve el source normalizado (black + ruff --fix), o None si black no puede formatearlo.
    Adoptar la versión limpia hace práctico el coder local: clava la LÓGICA, no el espaciado."""
    try:
        import black

        formateado = black.format_str(source, mode=black.Mode())
    except ImportError:
        return source, "black no disponible (sin normalizar)"
    except Exception as exc:  # noqa: BLE001 — black no pudo: no es código formateable
        return None, f"black no pudo formatear: {exc}"
    return _ruff_fix(formateado), "normalizado (black + ruff --fix)"


def _ruff_fix(source: str) -> str:
    """Aplica los autofixes de ruff (imports sin usar, etc.) y reformatea. Best-effort sobre un
    fichero temporal (ruff --fix opera sobre ficheros)."""
    ruta = ""
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(source)
            ruta = f.name
        subprocess.run(
            [sys.executable, "-m", "ruff", "check", "--fix", "--quiet", ruta],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=_TIMEOUT,
        )
        with open(ruta, encoding="utf-8") as fh:
            fijado = fh.read()
    except Exception:  # noqa: BLE001 — sin ruff o sin temp, devuelve lo que había
        return source
    finally:
        if ruta:
            try:
                os.unlink(ruta)
            except OSError:
                pass
    try:
        import black

        return black.format_str(fijado, mode=black.Mode())
    except Exception:  # noqa: BLE001
        return fijado


def _check_ruff(source: str) -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "ruff", "check", "--stdin-filename", "tool_fabrica.py", "-"],
            input=source,
            capture_output=True,
            text=True,
            encoding="utf-8",  # Windows: ruff lee stdin como UTF-8 (evita 'invalid UTF-8')
            timeout=_TIMEOUT,
        )
    except FileNotFoundError:
        return True, "ruff no ejecutable (omitido)"
    except subprocess.TimeoutExpired:
        return False, "ruff agotó el tiempo"
    if proc.returncode == 0:
        return True, "lint ruff OK"
    salida = (proc.stdout or proc.stderr or "").strip().splitlines()
    return False, "ruff: " + " | ".join(salida[:4])


def _importar(borrador: BorradorTool):
    """Compila e importa el source en un namespace aislado (builtins recortados + import seguro).
    Ya pasó el gate estático de seguridad; este entorno es la defensa dinámica."""
    ns = construir_namespace_seguro()
    try:
        exec(
            compile(borrador.source, "<fabrica_tool>", "exec"), ns
        )  # noqa: S102 — vetado por seguridad
    except Exception as exc:  # noqa: BLE001 — cualquier fallo de import es un rechazo limpio
        return None, f"no importa: {exc!r}"
    fn = ns.get(borrador.nombre)
    if not callable(fn):
        return None, f"'{borrador.nombre}' no es invocable tras importar"
    return fn, "importa e invocable"


def _correr_eval(borrador: BorradorTool, fn) -> tuple[bool, str]:
    """El eval_source debe definir `check(fn) -> tuple[bool, str]`. Sin eval, puerta en rojo."""
    if not (borrador.eval_source or "").strip():
        return False, "falta eval de comportamiento (una tool útil trae su prueba — DoD)"
    ns = construir_namespace_seguro()
    try:
        exec(compile(borrador.eval_source, "<fabrica_eval>", "exec"), ns)  # noqa: S102 — vetado
        check = ns.get("check")
        if not callable(check):
            return False, "el eval_source no define check(fn)"
        resultado = check(fn)
    except Exception as exc:  # noqa: BLE001
        return False, f"el eval reventó: {exc!r}"
    if isinstance(resultado, tuple) and len(resultado) == 2:
        ok, detalle = bool(resultado[0]), str(resultado[1])
        return ok, detalle
    return bool(resultado), "eval devolvió un booleano"


def _check_sin_regresion() -> tuple[bool, str]:
    """El eval-set existente debe seguir verde: lo nuevo no puede romper lo que ya funcionaba."""
    try:
        from ..selfcheck import run_selfcheck

        res = run_selfcheck()
    except Exception as exc:  # noqa: BLE001
        return False, f"no se pudo correr el selfcheck: {exc!r}"
    if res.get("ok"):
        return True, f"sin regresión ({res.get('verdes', 0)}/{res.get('total', 0)} verdes)"
    return False, f"regresión: fallan {', '.join(res.get('fallos', [])) or res.get('error', '?')}"
