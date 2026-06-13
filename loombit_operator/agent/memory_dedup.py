"""
memory_dedup.py — consolidación de lecciones: dedup por EXACTO + NEAR-DUPLICADO (estilo Mem0).

Sacado fuera de `memory.py` a propósito: ese fichero está en deuda de tamaño (>400 líneas, ratchet de
la Brújula) y NO puede engordar. Aquí vive la lógica nueva, determinista y sin red. Se enchufa en el
daemon de consolidación (`aprendizaje.py`), que es donde se acumulan lecciones en lote.

El dedup SEMÁNTICO real (paráfrasis con OTRO vocabulario, p.ej. «email» vs «correo») necesita
EMBEDDINGS (el modelo) → queda 🟠 DECLARADO (D-95): engancharlo al RAG local es el siguiente paso.
"""

from __future__ import annotations

import re

# Solape de tokens (Jaccard) a partir del cual dos lecciones se tratan como NEAR-DUPLICADO. Tunable.
UMBRAL_DEDUP_LECCION = 0.7


def tokens_de(text: str, tags: list[str] | None = None) -> set[str]:
    """Tokens significativos (≥4 chars) de una lección — mismo criterio que `LessonEntry.tokens`."""
    words = (str(text) + " " + " ".join(tags or [])).lower()
    return {w for w in re.findall(r"[a-záéíóúñ0-9]+", words) if len(w) >= 4}


def solape_jaccard(a: set[str], b: set[str]) -> float:
    """Solape de Jaccard entre dos conjuntos de tokens (0..1); 0 si alguno está vacío."""
    if not a or not b:
        return 0.0
    union = len(a | b)
    return len(a & b) / union if union else 0.0


def leccion_duplicada(text: str, tags: list[str] | None, lecciones: list[dict]) -> dict | None:
    """Devuelve el dict de la lección existente a REFORZAR si `text` es duplicado EXACTO o
    NEAR-DUPLICADO (solape de tokens ≥ `UMBRAL_DEDUP_LECCION`) de alguna; si no, None.

    `lecciones` = lista de dicts con al menos `text` (y opcional `tags`). Determinista, sin red.
    """
    text_l = str(text).strip().lower()
    nuevos = tokens_de(text, tags)
    for x in lecciones:
        existente = str(x.get("text", "")).strip()
        if existente.lower() == text_l:
            return x
        if solape_jaccard(nuevos, tokens_de(existente, x.get("tags"))) >= UMBRAL_DEDUP_LECCION:
            return x
    return None
