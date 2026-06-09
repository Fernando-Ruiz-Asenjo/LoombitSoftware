"""
rag.py — índice semántico LOCAL (Skill W, núcleo blanco). El fundamento del P1.

Un administrativo con oficio no busca por palabra exacta: recuerda por SENTIDO. Esto da a Loombit esa
memoria: vectoriza el histórico (ejecuciones, lecciones, empresas, contactos, procedimientos) con el
modelo de embeddings LOCAL (nomic-embed vía LM Studio) y busca por SIMILITUD de significado, no por
coincidencia de tokens. Local-first: los vectores nunca salen de la máquina; se persisten en
`runtime/local/rag_index.json`.

Desbloquea: búsqueda en el histórico, procedencia ("¿de dónde saqué esto?"), estilo propio (recuperar
mis correos parecidos) y la memoria del galaxia. Determinista para tests: `embed_fn` es inyectable.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .config import AppSettings, get_settings

EmbedFn = Callable[[list[str]], list[list[float]]]


@dataclass
class Documento:
    """Una unidad indexable: su id estable, el texto, metadatos y (tras indexar) su vector."""

    id: str
    text: str
    meta: dict[str, Any] = field(default_factory=dict)
    vector: list[float] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "text": self.text, "meta": self.meta, "vector": self.vector}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Documento":
        return cls(
            id=str(d["id"]),
            text=str(d.get("text", "")),
            meta=dict(d.get("meta", {})),
            vector=[float(x) for x in d.get("vector", [])],
        )


def _coseno(a: list[float], b: list[float]) -> float:
    """Similitud coseno (pura, sin numpy). 0 si algún vector es nulo o de distinta dimensión."""
    if not a or not b or len(a) != len(b):
        return 0.0
    num = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return num / (na * nb)


class SemanticIndex:
    """Índice vectorial local con persistencia JSON. `embed_fn` por defecto = el modelo de LM Studio
    (inyectable para tests). Dedup por id: re-indexar un id lo actualiza, no lo duplica."""

    def __init__(
        self,
        path: Path | None = None,
        embed_fn: EmbedFn | None = None,
        settings: AppSettings | None = None,
    ) -> None:
        active = settings or get_settings()
        self.path = path or active.rag_index_path
        self.model = active.llm_embeddings_model_name
        self._embed_fn = embed_fn
        self._docs: dict[str, Documento] = {}
        self._load()

    # ── Embedder (lazy: no crea cliente LLM hasta que se necesita de verdad) ────
    def _embed(self, textos: list[str]) -> list[list[float]]:
        if not textos:
            return []
        if self._embed_fn is not None:
            return self._embed_fn(textos)
        from .llm import LLMClient

        return LLMClient().embed(textos)

    # ── Escritura ───────────────────────────────────────────────────────────────
    def add(self, doc_id: str, text: str, meta: dict[str, Any] | None = None) -> None:
        self.add_many([Documento(id=doc_id, text=text, meta=meta or {})])

    def add_many(self, docs: list[Documento]) -> int:
        """Vectoriza e indexa (o actualiza) los documentos con texto no vacío. Devuelve cuántos."""
        utiles = [d for d in docs if (d.text or "").strip()]
        if not utiles:
            return 0
        vectores = self._embed([d.text for d in utiles])
        n = 0
        for doc, vec in zip(utiles, vectores):
            if not vec:
                continue
            doc.vector = [float(x) for x in vec]
            self._docs[doc.id] = doc
            n += 1
        if n:
            self._save()
        return n

    # ── Lectura ──────────────────────────────────────────────────────────────────
    def search(self, query: str, k: int = 5, fuente: str | None = None) -> list[dict[str, Any]]:
        """Top-k por similitud de significado. `fuente` filtra por meta['fuente'] (history/lesson/…)."""
        if not (query or "").strip() or not self._docs:
            return []
        qv = self._embed([query])
        if not qv or not qv[0]:
            return []
        qvec = qv[0]
        candidatos = [
            d for d in self._docs.values() if not fuente or d.meta.get("fuente") == fuente
        ]
        puntuados = [(_coseno(qvec, d.vector), d) for d in candidatos]
        puntuados.sort(key=lambda p: p[0], reverse=True)
        return [
            {"id": d.id, "score": round(s, 4), "text": d.text, "meta": d.meta}
            for s, d in puntuados[:k]
            if s > 0
        ]

    def stats(self) -> dict[str, Any]:
        por_fuente: dict[str, int] = {}
        for d in self._docs.values():
            f = str(d.meta.get("fuente", "?"))
            por_fuente[f] = por_fuente.get(f, 0) + 1
        dims = next((len(d.vector) for d in self._docs.values() if d.vector), 0)
        return {
            "store_path": str(self.path),
            "model": self.model,
            "count": len(self._docs),
            "dim": dims,
            "por_fuente": por_fuente,
        }

    # ── Construcción del corpus desde la memoria operativa real ───────────────────
    def reindexar_memoria(self, memoria: Any = None, max_history: int = 400) -> dict[str, Any]:
        """Indexa el histórico real: ejecuciones, lecciones, empresas, contactos y procedimientos.
        Es el corpus 'de dentro' (lo que Loombit ya vivió). Idempotente por id estable."""
        if memoria is None:
            from .agent.memory import get_memory

            memoria = get_memory()
        docs: list[Documento] = []
        for i, h in enumerate(memoria.history[:max_history]):
            docs.append(
                Documento(
                    id=f"history:{h.run_id or i}",
                    text=f"{h.task} → {h.result}",
                    meta={"fuente": "history", "fecha": h.date, "run_id": h.run_id},
                )
            )
        for i, le in enumerate(memoria.lessons):
            docs.append(
                Documento(
                    id=f"lesson:{i}", text=le.text, meta={"fuente": "lesson", "outcome": le.outcome}
                )
            )
        for prof in memoria.entities.values():
            docs.append(
                Documento(
                    id=f"entity:{prof.nif or prof.name}",
                    text=str(prof),
                    meta={"fuente": "entity", "name": prof.name},
                )
            )
        for c in memoria.contacts:
            docs.append(
                Documento(
                    id=f"contact:{c.email}", text=str(c), meta={"fuente": "contact", "name": c.name}
                )
            )
        for key, proc in memoria.procedures.items():
            docs.append(
                Documento(id=f"procedure:{key}", text=str(proc), meta={"fuente": "procedure"})
            )
        indexados = self.add_many(docs)
        return {"indexados": indexados, "vistos": len(docs), **self.stats()}

    # ── Persistencia ───────────────────────────────────────────────────────────
    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8") or "{}")
        except (json.JSONDecodeError, OSError):
            return
        self._docs = {
            str(d["id"]): Documento.from_dict(d) for d in raw.get("items", []) if d.get("id")
        }

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": 1,
            "model": self.model,
            "items": [d.to_dict() for d in self._docs.values()],
        }
        tmp = self.path.with_suffix(f"{self.path.suffix}.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)


_index: SemanticIndex | None = None


def get_index() -> SemanticIndex:
    """Singleton del índice (usa el modelo real de embeddings)."""
    global _index
    if _index is None:
        _index = SemanticIndex()
    return _index
