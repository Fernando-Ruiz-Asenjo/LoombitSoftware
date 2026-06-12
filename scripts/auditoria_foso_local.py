"""
auditoria_foso_local.py — ALGORITMO DEL FOSO «LOCAL» (NORTE). Un algoritmo por norma (§GOB-2).

Norma defendida: *los datos del usuario NO salen de la máquina*. Es el foso nº1 de Loombit. Este algoritmo
lo vuelve binario: recorre el código del producto (`loombit_operator/`), extrae por AST cada URL/host que
aparece en una cadena de CÓDIGO (NO en comentarios ni docstrings — esos no son egress) y exige que TODO
destino esté en una ALLOWLIST declarada. Un destino nuevo a la nube que nadie declaró → gate ROJO.

No decide la visión ("¿es bueno el foso?"); decide un PROXY verificable: ningún host de egress sin declarar.
Determinista, puro, sin red. Mismo patrón que `cifra_parser` (allowlist + lo nuevo se declara o se bloquea).

Residuo declarado (honesto): caza URLs LITERALES en el código. Un destino construido en runtime desde una
variable/setting no se resuelve estáticamente → lo cubre el guardia de egress en runtime (futuro, v2). El
LLM local (LM Studio) y el servidor son `localhost`, declarados abajo.
"""

from __future__ import annotations

import argparse
import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRODUCTO = ROOT / "loombit_operator"

# ── ALLOWLIST declarada (a la vista, con su PORQUÉ). Tres categorías. ──────────────────────────────
LOCAL = {
    "127.0.0.1",  # servidor FastAPI + LLM local (LM Studio)
    "localhost",
    "0.0.0.0",  # bind local
}
CONECTORES_CONSENTIDOS = {
    # Google Workspace — OAuth que el usuario conecta explícitamente (Gmail/Calendar/Drive/People).
    "gmail.googleapis.com",
    "www.googleapis.com",
    "people.googleapis.com",
    "oauth2.googleapis.com",
    "accounts.google.com",
    "mail.google.com",
    "calendar.google.com",
    # Microsoft Graph — OAuth consentido (Outlook/Calendar).
    "login.microsoftonline.com",
    "graph.microsoft.com",
}
LECTURA_PUBLICA = {
    # Solo LEEN web pública (radar/innovación + fiscal). NO envían datos del usuario.
    "news.ycombinator.com",
    "hn.algolia.com",
    "export.arxiv.org",
    "www.boe.es",
    "api.github.com",
}
_CATEGORIA = (
    [(h, "LOCAL") for h in LOCAL]
    + [(h, "CONECTOR_CONSENTIDO") for h in CONECTORES_CONSENTIDOS]
    + [(h, "LECTURA_PUBLICA") for h in LECTURA_PUBLICA]
)
ALLOWLIST: dict[str, str] = dict(_CATEGORIA)

_RE_URL = re.compile(r"https?://([^/\s:'\")]+)", re.IGNORECASE)
# Host real = al menos una etiqueta + un punto (dominio) o una IP. Filtra placeholders tipo «...».
_RE_HOST_REAL = re.compile(r"^[a-z0-9-]+(\.[a-z0-9-]+)+$", re.IGNORECASE)


def host_de_url(url: str) -> str | None:
    """Saca el host de una URL y le quita el puerto. None si no hay host."""
    m = _RE_URL.search(url)
    if not m:
        return None
    return m.group(1).split(":")[0].strip().lower()


def es_host_real(host: str) -> bool:
    """¿Es un host de verdad (dominio o IP) y no un placeholder («...», «host», vacío)?"""
    return host in LOCAL or bool(_RE_HOST_REAL.match(host))


def clasificar(host: str) -> str | None:
    """Categoría del host en la allowlist, o None si NO está declarado (= violación del foso)."""
    return ALLOWLIST.get(host)


def _ids_docstrings(tree: ast.AST) -> set[int]:
    """ids de los nodos Constant que son docstrings (módulo/clase/función): NO son egress, se ignoran."""
    out: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            cuerpo = getattr(node, "body", [])
            if (
                cuerpo
                and isinstance(cuerpo[0], ast.Expr)
                and isinstance(cuerpo[0].value, ast.Constant)
                and isinstance(cuerpo[0].value.value, str)
            ):
                out.add(id(cuerpo[0].value))
    return out


def hosts_en_fuente(codigo: str) -> list[str]:
    """Hosts REALES que aparecen en cadenas de CÓDIGO (sin docstrings ni comentarios), vía AST."""
    tree = ast.parse(codigo)
    docs = _ids_docstrings(tree)
    hosts: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs:
            for m in _RE_URL.finditer(node.value):
                host = m.group(1).split(":")[0].strip().lower()
                if es_host_real(host):
                    hosts.append(host)
    return hosts


def auditar_repo() -> list[tuple[str, str]]:
    """Recorre el producto y devuelve los (fichero, host) cuyo destino NO está en la allowlist."""
    violaciones: list[tuple[str, str]] = []
    for path in sorted(PRODUCTO.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            codigo = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for host in hosts_en_fuente(codigo):
            if clasificar(host) is None:
                rel = str(path.relative_to(ROOT))
                if (rel, host) not in violaciones:
                    violaciones.append((rel, host))
    return violaciones


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Algoritmo del foso LOCAL: ningún egress sin declarar.")
    p.add_argument("--list", action="store_true", help="lista los hosts declarados y sale")
    args = p.parse_args(argv)
    if args.list:
        for host, cat in sorted(ALLOWLIST.items()):
            print(f"  {cat:20} {host}")
        return 0
    violaciones = auditar_repo()
    if violaciones:
        print(f"== FOSO LOCAL ROJO: {len(violaciones)} destino(s) de egress SIN declarar ==")
        for rel, host in violaciones:
            print(f"  ❌ {host}  ({rel})")
        print(
            "  → si es legítimo, decláralo en la ALLOWLIST con su categoría y porqué; si no, QUÍTALO."
        )
        return 1
    print(
        f"== foso LOCAL VERDE: 0 destinos sin declarar ({len(ALLOWLIST)} hosts en la allowlist) =="
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
