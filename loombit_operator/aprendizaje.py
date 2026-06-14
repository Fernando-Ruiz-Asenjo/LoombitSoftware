"""
aprendizaje.py — consolidación PROACTIVA de la memoria (cierra la Fase 5: memoria y aprendizaje).

El bucle del agente ya aprende POR-RUN (Reflexion en fallos + contactos + historial + procedimientos,
ver `agent/loop.py`). Esto es el lazo PROGRAMADO que consolida en 2º plano, lo que faltaba para cerrar
la fase:
  1. **Mantiene fresco el índice semántico (RAG):** reindexa el histórico para que `memory_search`
     recupere por significado lo último, sin que se quede obsoleto.
  2. **Destila lecciones generales (Reflexion proactiva):** revisa las últimas ejecuciones y extrae
     lecciones reutilizables (no solo de los fallos del momento). Idempotente: `add_lesson` deduplica
     por texto, así que repetir el ciclo no infla la memoria.

Sin efecto externo (PASSIVE): solo lee y escribe en memoria/índice LOCALES. Best-effort: nunca lanza;
cada parte informa su resultado. Todo inyectable para tests (sin LM Studio).
"""

from __future__ import annotations

from typing import Any, Callable


def consolidar(
    *,
    index: Any = None,
    memoria: Any = None,
    store_runs: Any = None,
    reflexionar_fn: Callable[[Any, Any], str | None] | None = None,
    etiquetas_fn: Callable[[str], list[str]] | None = None,
    llm: Any = None,
    max_runs: int = 0,
) -> dict[str, Any]:
    """Consolida la memoria: reindexa el RAG y (si `max_runs>0`) destila lecciones de runs recientes.
    Devuelve un informe {docs, dim, indexados, lecciones_nuevas, runs_revisados, resumen, errores}.

    `max_runs=0` por defecto: el daemon hace SOLO el reindexado (rápido y fiable; su valor único es
    mantener fresca la memoria semántica). La Reflexion proactiva sobre el histórico hace VARIAS
    llamadas al 14B —costosa en este hardware, puede exceder el cupo del scheduler— así que es OPT-IN
    (súbela en hardware más rápido/Jetson). El aprendizaje por-run ya ocurre en el loop del agente.
    Inyecta `index`/`memoria`/`store_runs`/`reflexionar_fn` para tests; por defecto usa los reales.
    """
    errores: list[str] = []
    docs = dim = indexados = 0
    lecciones_nuevas = runs_revisados = 0

    # ── 1. Índice semántico fresco ─────────────────────────────────────────────
    try:
        if index is None:
            from .rag import get_index

            index = get_index()
        info = index.reindexar_memoria(memoria=memoria)
        docs = int(info.get("count", 0))
        dim = int(info.get("dim", 0))
        indexados = int(info.get("indexados", 0))
    except Exception as exc:  # noqa: BLE001 — el aprendizaje nunca rompe; informa con honestidad
        errores.append(f"índice: {exc!r}")

    # ── 2. Reflexion proactiva sobre los runs recientes (OPT-IN: max_runs>0) ──
    # max_runs=0 (defecto del daemon): reindex-only, no se toca el 14B → rápido y nunca falla.
    if max_runs > 0:
        try:
            if memoria is None:
                from .agent.memory import get_memory

                memoria = get_memory()
            if store_runs is None:
                from .agent.run import AgentStore

                store_runs = AgentStore()
            if reflexionar_fn is None or etiquetas_fn is None:
                from .agent.reflexion import etiquetas_de_tarea, reflexionar

                reflexionar_fn = reflexionar_fn or reflexionar
                etiquetas_fn = etiquetas_fn or etiquetas_de_tarea
            if llm is None:
                from .llm import LLMClient

                llm = LLMClient()

            from .agent.memory_dedup import leccion_duplicada  # dedup near-dup (D-95)

            vistas = [le.to_dict() for le in memoria.lessons]
            runs = list(store_runs.list())[:max_runs]
            runs_revisados = len(runs)
            for run in runs:
                leccion = reflexionar_fn(run, llm)
                if not leccion:
                    continue
                tags = etiquetas_fn(getattr(run, "task", ""))
                # Consolidación estilo Mem0: si es duplicada EXACTA o NEAR-DUPLICADA, no acumular ruido.
                if leccion_duplicada(leccion, tags, vistas) is not None:
                    continue
                memoria.add_lesson(leccion, tags=tags, source="reflexion_proactiva")
                vistas.append({"text": leccion.strip(), "tags": [t.lower() for t in tags]})
                lecciones_nuevas += 1
        except Exception as exc:  # noqa: BLE001
            errores.append(f"lecciones: {exc!r}")

    partes = [
        f"índice {docs} docs ({dim}d)",
        f"{lecciones_nuevas} lección(es) nueva(s) de {runs_revisados} run(s)",
    ]
    resumen = (
        "Aprendizaje: "
        + " · ".join(partes)
        + (f" · errores: {'; '.join(errores)}" if errores else "")
        + "."
    )
    return {
        "docs": docs,
        "dim": dim,
        "indexados": indexados,
        "lecciones_nuevas": lecciones_nuevas,
        "runs_revisados": runs_revisados,
        "errores": errores,
        "resumen": resumen,
    }
