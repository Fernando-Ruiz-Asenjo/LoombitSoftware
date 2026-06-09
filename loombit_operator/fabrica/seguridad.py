"""
seguridad.py — gate de seguridad estático del código AUTO-ESCRITO (linchpin de la Fábrica).

El código que el modelo coder propone NO se ejecuta ni se importa hasta que pasa este
análisis. Es una lista-blanca estricta sobre el AST: si algo no está permitido, se rechaza
(seguro-por-defecto). No es heurística difusa: razona sobre nodos concretos del árbol.

Qué bloquea (las vías reales de escape de un sandbox Python):
- `import`/`from` de módulos peligrosos (os, sys, subprocess, socket, importlib, ctypes,
  pickle, threading, inspect, red/ficheros…). Solo se permite una raíz de stdlib segura.
- llamadas a `eval`, `exec`, `compile`, `__import__`, `open`, `globals`, `getattr`…
- accesos a dunders de introspección (`__globals__`, `__subclasses__`, `__class__`…),
  el camino clásico para llegar a `os` sin importarlo.

Una tool de v1 es de cómputo puro (fechas, parsing, cálculo fiscal determinista, formato):
útil y sin necesidad de red ni ficheros. Capacidades con efectos (red, disco, envío) exigen
una propuesta más profunda con revisión humana — no se cuelan por aquí.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field

# Raíces de import permitidas: stdlib de cómputo puro, sin red, disco, procesos ni introspección.
MODULOS_PERMITIDOS: frozenset[str] = frozenset(
    {
        "json",
        "re",
        "math",
        "decimal",
        "fractions",
        "datetime",
        "time",
        "calendar",
        "typing",
        "dataclasses",
        "collections",
        "itertools",
        "functools",
        "statistics",
        "unicodedata",
        "html",
        "string",
        "textwrap",
        "enum",
        "zoneinfo",
        "uuid",
        "random",
        "base64",
        "hashlib",
        "hmac",
        "abc",
        "contextlib",
        "numbers",
        "bisect",
        "operator",
    }
)

# Nombres de función prohibidos en cualquier llamada (vías de ejecución arbitraria / IO).
LLAMADAS_PROHIBIDAS: frozenset[str] = frozenset(
    {
        "eval",
        "exec",
        "compile",
        "__import__",
        "open",
        "globals",
        "locals",
        "vars",
        "getattr",
        "setattr",
        "delattr",
        "input",
        "breakpoint",
        "memoryview",
        "exit",
        "quit",
        "help",
    }
)

# Dunders cuyo acceso es un vector de escape de sandbox conocido.
DUNDERS_PROHIBIDOS: frozenset[str] = frozenset(
    {
        "__globals__",
        "__builtins__",
        "__subclasses__",
        "__bases__",
        "__mro__",
        "__class__",
        "__dict__",
        "__code__",
        "__closure__",
        "__getattribute__",
        "__reduce__",
        "__reduce_ex__",
        "__import__",
        "__loader__",
        "__spec__",
    }
)


@dataclass
class ResultadoSeguridad:
    """Veredicto del gate estático. `ok` solo si NO hay ninguna violación."""

    ok: bool
    violaciones: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {"ok": self.ok, "violaciones": list(self.violaciones)}


def _raiz(modulo: str | None) -> str:
    return (modulo or "").split(".", 1)[0]


class _Inspector(ast.NodeVisitor):
    """Recorre el AST y acumula violaciones con su línea."""

    def __init__(self) -> None:
        self.violaciones: list[str] = []

    def _v(self, nodo: ast.AST, msg: str) -> None:
        linea = getattr(nodo, "lineno", "?")
        self.violaciones.append(f"L{linea}: {msg}")

    def visit_Import(self, nodo: ast.Import) -> None:
        for alias in nodo.names:
            raiz = _raiz(alias.name)
            if raiz not in MODULOS_PERMITIDOS:
                self._v(nodo, f"import no permitido: '{alias.name}'")
        self.generic_visit(nodo)

    def visit_ImportFrom(self, nodo: ast.ImportFrom) -> None:
        if nodo.level and nodo.level > 0:
            self._v(nodo, "import relativo no permitido")
        elif _raiz(nodo.module) not in MODULOS_PERMITIDOS:
            self._v(nodo, f"from-import no permitido: '{nodo.module}'")
        self.generic_visit(nodo)

    def visit_Call(self, nodo: ast.Call) -> None:
        fn = nodo.func
        if isinstance(fn, ast.Name) and fn.id in LLAMADAS_PROHIBIDAS:
            self._v(nodo, f"llamada prohibida: '{fn.id}(...)'")
        elif isinstance(fn, ast.Attribute) and fn.attr in LLAMADAS_PROHIBIDAS:
            self._v(nodo, f"llamada prohibida: '.{fn.attr}(...)'")
        self.generic_visit(nodo)

    def visit_Attribute(self, nodo: ast.Attribute) -> None:
        if nodo.attr in DUNDERS_PROHIBIDOS:
            self._v(nodo, f"acceso a dunder peligroso: '.{nodo.attr}'")
        self.generic_visit(nodo)

    def visit_Name(self, nodo: ast.Name) -> None:
        if nodo.id in DUNDERS_PROHIBIDOS:
            self._v(nodo, f"uso de dunder peligroso: '{nodo.id}'")
        self.generic_visit(nodo)


def analizar_seguridad(source: str) -> ResultadoSeguridad:
    """Analiza el `source` de una tool auto-escrita. `ok=True` solo si es seguro importarlo.

    No ejecuta nada: solo parsea y recorre el AST. Si el código no compila, también es un
    rechazo (no es una tool válida)."""
    try:
        arbol = ast.parse(source)
    except SyntaxError as exc:
        return ResultadoSeguridad(ok=False, violaciones=[f"no compila: {exc.msg} (L{exc.lineno})"])

    inspector = _Inspector()
    inspector.visit(arbol)
    return ResultadoSeguridad(ok=not inspector.violaciones, violaciones=inspector.violaciones)


# ── Sandbox de ejecución (defensa en profundidad: además del gate estático) ──────

# Builtins que NUNCA entran al namespace de una tool auto-escrita (vías de IO / ejecución).
_BUILTINS_VETADOS: frozenset[str] = frozenset(
    {
        "eval",
        "exec",
        "compile",
        "open",
        "input",
        "breakpoint",
        "help",
        "exit",
        "quit",
        "globals",
        "locals",
        "vars",
        "memoryview",
        "getattr",
        "setattr",
        "delattr",
        "__import__",
    }
)


def _import_seguro(name: str, *args: object, **kwargs: object) -> object:
    """`__import__` recortado: solo deja importar la allowlist (corta imports dinámicos que el
    análisis estático no vería). Es el cinturón sobre los tirantes del gate AST."""
    import builtins

    if name.split(".", 1)[0] not in MODULOS_PERMITIDOS:
        raise ImportError(f"import bloqueado por la Fábrica: '{name}'")
    return builtins.__import__(name, *args, **kwargs)  # type: ignore[arg-type]


def construir_namespace_seguro() -> dict[str, object]:
    """Namespace aislado para `exec` de código auto-escrito: builtins recortados + import seguro.
    Patrón estándar 2025 (smolagents/LLM-Sandbox): el AST veta de forma estática y este entorno
    veta de forma dinámica. Aun así, el código solo se ejecuta tras pasar `analizar_seguridad`."""
    import builtins

    seguros = {
        nombre: obj
        for nombre, obj in vars(builtins).items()
        if nombre not in _BUILTINS_VETADOS and not nombre.startswith("__")
    }
    seguros["__import__"] = _import_seguro
    return {"__builtins__": seguros}
