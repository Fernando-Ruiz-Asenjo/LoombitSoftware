"""
red.py — fuente EXTERNA de la Fábrica: un RADAR de inteligencia que trae mejoras de la Red.

"Lo de fuera, para traer cosas útiles." NO es leer el BOE: es mirar qué hace el mundo y traerlo:
- **GitHub**   → qué agentes/skills/tools construyen los demás ("ver qué hacen" y traerlo aquí).
- **HackerNews** → mercado, competencia, noticias, lanzamientos, tendencias.
- **arXiv**    → nuevas técnicas/papers aplicables.
- **BOE**      → normativa española (uno más del radar, no el centro).

Cada hallazgo es una `Necesidad(fuente=RED)` CON procedencia (URL) — nunca un dato sin fuente. Usa
APIs públicas y gratuitas (sin clave) vía httpx; cada canal es best-effort (si la Red falla, []).
El abanico de canales es expandible (ProductHunt, RSS de competidores, changelogs…). Y los barridos
profundos de Claude (competencia/monetización) alimentan este mismo radar.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from .modelos import Fuente, Necesidad, TipoNecesidad

MADRID = ZoneInfo("Europe/Madrid")
_TIMEOUT = 15
_UA = {"User-Agent": "Loombit-Operator-Radar"}

# Consultas alineadas con el foso (operador administrativo local + agentes que se automejoran).
_Q_GITHUB = ("autonomous accounting AI agent", "AI agent skills framework")
_Q_HN = ("AI agent startup", "AI accounting automation")
_Q_ARXIV = ("self-improving LLM agent", "LLM agent tool creation")


def _get(http_get: Any, url: str, **kw: Any) -> Any | None:
    """GET best-effort: devuelve la respuesta o None si la Red falla. Sigue redirects (arXiv hace
    http→https) salvo cuando se inyecta `http_get` (tests)."""
    try:
        if http_get is None:
            resp = httpx.get(url, timeout=_TIMEOUT, follow_redirects=True, **kw)
        else:
            resp = http_get(url, timeout=_TIMEOUT, **kw)
    except Exception:  # noqa: BLE001 — la Red puede fallar; un canal caído no rompe el radar
        return None
    if getattr(resp, "status_code", 200) != 200:
        return None
    return resp


# ── Canal GitHub: ¿qué agentes/skills/tools construyen los demás? ────────────────


def canal_github(
    http_get: Any = None, max_items: int = 3, queries: tuple[str, ...] = _Q_GITHUB
) -> list[Necesidad]:
    necesidades: list[Necesidad] = []
    for q in queries:
        resp = _get(
            http_get,
            "https://api.github.com/search/repositories",
            headers={**_UA, "Accept": "application/vnd.github+json"},
            params={"q": q, "sort": "stars", "order": "desc", "per_page": max_items},
        )
        if resp is None:
            continue
        for repo in (resp.json() or {}).get("items", [])[:max_items]:
            estrellas = repo.get("stargazers_count", 0)
            desc = (repo.get("description") or "").strip()[:160]
            necesidades.append(
                Necesidad(
                    titulo=f"GitHub: '{repo.get('full_name')}' ({estrellas}★) — {desc}",
                    tipo=TipoNecesidad.SKILL,
                    fuente=Fuente.RED,
                    descripcion=(
                        f"Proyecto puntero en '{q}'. Ver qué resuelve y evaluar traer la capacidad "
                        "a Loombit (como skill/tool, adaptada al foso local+español)."
                    ),
                    evidencia=[desc] if desc else [],
                    prioridad=2 + min(int(estrellas) // 3000, 4),  # más estrellas, más señal
                    procedencia=[repo.get("html_url", "")],
                )
            )
    return necesidades


# ── Canal Hacker News: mercado, competencia, noticias ───────────────────────────


def canal_hackernews(
    http_get: Any = None, max_items: int = 3, queries: tuple[str, ...] = _Q_HN
) -> list[Necesidad]:
    necesidades: list[Necesidad] = []
    for q in queries:
        resp = _get(
            http_get,
            "https://hn.algolia.com/api/v1/search",
            params={"query": q, "tags": "story", "hitsPerPage": max_items},
        )
        if resp is None:
            continue
        for hit in (resp.json() or {}).get("hits", [])[:max_items]:
            titulo = (hit.get("title") or "").strip()
            if not titulo:
                continue
            url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
            necesidades.append(
                Necesidad(
                    titulo=f"Mercado/competencia (HN, {hit.get('points', 0)}pts): {titulo[:110]}",
                    tipo=TipoNecesidad.MEJORA,
                    fuente=Fuente.RED,
                    descripcion=(
                        f"Tendencia/competidor sobre '{q}'. Leer y destilar qué hace y si abre una "
                        "vía (capacidad nueva o monetización) para Loombit."
                    ),
                    evidencia=[titulo[:240]],
                    prioridad=3,
                    procedencia=[url],
                )
            )
    return necesidades


# ── Canal arXiv: nuevas técnicas aplicables ─────────────────────────────────────


def canal_arxiv(http_get: Any = None, max_items: int = 2) -> list[Necesidad]:
    necesidades: list[Necesidad] = []
    for q in _Q_ARXIV:
        resp = _get(
            http_get,
            "https://export.arxiv.org/api/query",
            params={"search_query": f'all:"{q}"', "max_results": max_items},
        )
        if resp is None:
            continue
        for titulo, enlace in _parse_arxiv(getattr(resp, "text", ""))[:max_items]:
            necesidades.append(
                Necesidad(
                    titulo=f"Nueva técnica (arXiv): {titulo[:110]}",
                    tipo=TipoNecesidad.MEJORA,
                    fuente=Fuente.RED,
                    descripcion=(
                        f"Paper reciente sobre '{q}'. Evaluar si la técnica es aplicable a Loombit "
                        "(p.ej. a la auto-evolución de skills o a la cognición)."
                    ),
                    evidencia=[titulo[:240]],
                    prioridad=2,
                    procedencia=[enlace],
                )
            )
    return necesidades


def _parse_arxiv(xml: str) -> list[tuple[str, str]]:
    """Saca (título, enlace) de cada <entry> del Atom de arXiv. Tolerante: regex, sin dependencias."""
    salida: list[tuple[str, str]] = []
    for entry in re.findall(r"<entry>(.*?)</entry>", xml, re.DOTALL):
        mt = re.search(r"<title>(.*?)</title>", entry, re.DOTALL)
        mi = re.search(r"<id>(.*?)</id>", entry, re.DOTALL)
        if mt and mi:
            titulo = re.sub(r"\s+", " ", mt.group(1)).strip()
            salida.append((titulo, mi.group(1).strip()))
    return salida


# ── Canal BOE: normativa española (uno más, no el centro) ───────────────────────

_BOE_RELEVANTE = (
    "autonomo",
    "autonomos",
    "iva",
    "irpf",
    "estimacion objetiva",
    "cotizacion",
    "verifactu",
    "factura electronica",
    "recargo de equivalencia",
    "trabajadores por cuenta propia",
)
# Coincidencia por PALABRA COMPLETA: evita el ruido de 'iva' dentro de 'archiva', 'deriva'…
_BOE_RE = re.compile(r"\b(" + "|".join(_BOE_RELEVANTE) + r")\b")


def _iter_boe(obj: Any) -> Iterator[dict[str, Any]]:
    if isinstance(obj, dict):
        if isinstance(obj.get("identificador"), str) and isinstance(obj.get("titulo"), str):
            yield obj
        for v in obj.values():
            yield from _iter_boe(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _iter_boe(v)


def canal_boe(http_get: Any = None, dias: int = 2, hoy: date | None = None) -> list[Necesidad]:
    hoy = hoy or datetime.now(MADRID).date()
    vistos: set[str] = set()
    necesidades: list[Necesidad] = []
    for delta in range(max(dias, 1)):
        dia = date.fromordinal(hoy.toordinal() - delta)
        resp = _get(
            http_get,
            f"https://www.boe.es/datosabiertos/api/boe/sumario/{dia.strftime('%Y%m%d')}",
            headers={"Accept": "application/json"},
        )
        if resp is None:
            continue
        for item in _iter_boe(resp.json()):
            ident, titulo = item["identificador"], item["titulo"]
            if ident in vistos or not _BOE_RE.search(titulo.lower()):
                continue
            vistos.add(ident)
            necesidades.append(
                Necesidad(
                    titulo=f"Normativa BOE (autónomos/PYME): {titulo[:100]}",
                    tipo=TipoNecesidad.MEJORA,
                    fuente=Fuente.RED,
                    descripcion="Disposición que puede afectar a Skill D Fiscal. Incorporar con cita.",
                    evidencia=[titulo[:240]],
                    prioridad=4,
                    procedencia=[f"BOE:{ident}", item.get("url_xml", "")],
                )
            )
    return necesidades


_CANALES = (canal_github, canal_hackernews, canal_arxiv, canal_boe)


def buscar_oportunidades_red(http_get: Any = None, max_items: int = 12) -> list[Necesidad]:
    """Lanza todos los canales del radar y agrega las oportunidades (más prioritarias primero).
    Best-effort por canal. Inyecta `http_get` en tests para no salir a la Red."""
    necesidades: list[Necesidad] = []
    for canal in _CANALES:
        try:
            necesidades += canal(http_get)
        except Exception:  # noqa: BLE001 — un canal que falla no tumba el radar
            continue
    # Dedup por procedencia (un mismo enlace puede salir de dos consultas).
    vistos: set[str] = set()
    unicas: list[Necesidad] = []
    for n in necesidades:
        clave = n.procedencia[0] if n.procedencia else n.titulo
        if clave in vistos:
            continue
        vistos.add(clave)
        unicas.append(n)
    unicas.sort(key=lambda n: n.prioridad, reverse=True)
    return unicas[:max_items]


def buscar_en_red(query: str, http_get: Any = None, max_items: int = 8) -> list[Necesidad]:
    """Búsqueda LIBRE en la Red (GitHub + HackerNews) sobre `query` — para "ver qué hace la
    competencia/el mercado en X" desde el chat. Best-effort, con cita. Dedup por URL."""
    necesidades = canal_github(http_get, queries=(query,)) + canal_hackernews(
        http_get, queries=(query,)
    )
    vistos: set[str] = set()
    unicas: list[Necesidad] = []
    for n in necesidades:
        clave = n.procedencia[0] if n.procedencia else n.titulo
        if clave and clave not in vistos:
            vistos.add(clave)
            unicas.append(n)
    return unicas[:max_items]
