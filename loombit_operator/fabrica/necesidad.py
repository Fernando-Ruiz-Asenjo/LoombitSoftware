"""
necesidad.py — detección DETERMINISTA de huecos ÚTILES (no micro-tweaks).

De dónde sale una necesidad real (con evidencia y procedencia, nunca inventada):
1. **El propio agente la pidió** — cada `propose_improvement(category="tool_missing", ...)` es el
   agente diciendo "no pude por falta de esta tool". Es la señal de oro: útil por definición.
2. **Una tool falla en bucle** — runs fallidos donde una misma tool devuelve error varias veces:
   candidata a arreglo (FIX).

La repetición pondera la prioridad (lo que más estorba se ataca antes). La detección es
determinista (cuenta y agrupa); el LLM no decide aquí qué construir, solo lo hará al redactar.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from .modelos import Necesidad, TipoNecesidad

_CATEGORIA_A_TIPO = {
    "tool_missing": TipoNecesidad.TOOL,
    "behavior": TipoNecesidad.FIX,
}
_SEÑAL_ERROR = ("[sistema", "error", "no encontr", "no pude", "falló", "fallo", "excep")


def _norm(texto: str) -> str:
    return re.sub(r"\s+", " ", (texto or "").strip().lower())


def _de_propuestas(proposals: list[Any]) -> list[Necesidad]:
    """Agrupa las carencias auto-reportadas por sugerencia; la repetición sube la prioridad."""
    grupos: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"issues": set(), "runs": set(), "categoria": "general", "sugerencia": ""}
    )
    for p in proposals:
        clave = _norm(getattr(p, "suggestion", "") or getattr(p, "issue", ""))
        if not clave:
            continue
        g = grupos[clave]
        g["sugerencia"] = getattr(p, "suggestion", "") or getattr(p, "issue", "")
        g["categoria"] = getattr(p, "category", "general") or "general"
        if getattr(p, "issue", ""):
            g["issues"].add(p.issue)
        if getattr(p, "run_id", ""):
            g["runs"].add(p.run_id)

    necesidades: list[Necesidad] = []
    for g in grupos.values():
        tipo = _CATEGORIA_A_TIPO.get(g["categoria"], TipoNecesidad.SKILL)
        veces = max(len(g["issues"]), 1)
        prioridad = veces * (2 if tipo == TipoNecesidad.TOOL else 1)
        procedencia = [f"agente:propose_improvement({g['categoria']})"]
        procedencia += [f"run:{r}" for r in sorted(g["runs"])][:5]
        necesidades.append(
            Necesidad(
                titulo=str(g["sugerencia"])[:120],
                tipo=tipo,
                descripcion="; ".join(sorted(g["issues"]))[:400],
                evidencia=sorted(g["issues"])[:5],
                prioridad=prioridad,
                procedencia=procedencia,
            )
        )
    return necesidades


def _de_runs_fallidos(runs: list[Any]) -> list[Necesidad]:
    """Tools que devuelven error en runs fallidos/cancelados: candidatas a arreglo (FIX)."""
    fallos: dict[str, dict[str, Any]] = defaultdict(lambda: {"n": 0, "runs": set(), "muestra": ""})
    for r in runs:
        estado = getattr(getattr(r, "status", None), "value", str(getattr(r, "status", "")))
        if estado not in ("failed", "cancelled"):
            continue
        for s in getattr(r, "steps", []):
            res = _norm(getattr(s, "result", ""))
            if res and any(t in res for t in _SEÑAL_ERROR):
                f = fallos[s.tool_name]
                f["n"] += 1
                f["runs"].add(getattr(r, "id", ""))
                f["muestra"] = f["muestra"] or getattr(s, "result", "")[:160]

    necesidades: list[Necesidad] = []
    for tool, f in fallos.items():
        if f["n"] < 2:  # un fallo aislado no es una necesidad; el patrón sí
            continue
        necesidades.append(
            Necesidad(
                titulo=f"Arreglar la tool '{tool}' que falla de forma recurrente",
                tipo=TipoNecesidad.FIX,
                descripcion=f"'{tool}' devolvió error en {f['n']} pasos de runs fallidos.",
                evidencia=[f["muestra"]] if f["muestra"] else [],
                prioridad=int(f["n"]),
                procedencia=[f"run:{r}" for r in sorted(f["runs"]) if r][:5],
            )
        )
    return necesidades


def detectar_necesidades(
    memoria: Any = None,
    store: Any = None,
    *,
    max_necesidades: int = 10,
) -> list[Necesidad]:
    """Mina las fuentes reales y devuelve las necesidades más prioritarias (mayor prioridad
    primero). Acepta `memoria`/`store` inyectados (tests); por defecto usa los reales."""
    if memoria is None:
        try:
            from ..agent.memory import get_memory

            memoria = get_memory()
        except Exception:  # noqa: BLE001 — sin memoria, simplemente no aporta señal
            memoria = None
    if store is None:
        try:
            from ..agent.run import AgentStore

            store = AgentStore()
        except Exception:  # noqa: BLE001
            store = None

    necesidades: list[Necesidad] = []
    if memoria is not None:
        try:
            necesidades += _de_propuestas(list(memoria.proposals))
        except Exception:  # noqa: BLE001
            pass
    if store is not None:
        try:
            necesidades += _de_runs_fallidos(store.list())
        except Exception:  # noqa: BLE001
            pass

    necesidades.sort(key=lambda n: n.prioridad, reverse=True)
    return necesidades[:max_necesidades]
