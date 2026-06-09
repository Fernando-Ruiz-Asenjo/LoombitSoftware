"""
higiene.py — higiene de afirmaciones para los hallazgos de la Red (lección OpenClaw, Mafia IA #06).

El radar (`red.py`) trae titulares de GitHub/HN/arXiv. Su texto es **dato, no instrucción**, y sus
cifras ("90% mejor", "10x", "$252B") son **afirmaciones sin verificar**. Antes de que un hallazgo de
la Red ascienda a algo accionable, se marca como "sin verificar" y se baja su prioridad: exige fuente
primaria + prueba, no adoptar por hype. Determinista, sin LLM. Solo toca lo de FUERA (Fuente.RED);
las señales de DENTRO (proceso/cognición) quedan intactas.
"""

from __future__ import annotations

import re

from .modelos import Fuente, Necesidad

# Afirmaciones a verificar: porcentajes, multiplicadores, dinero grande y superlativos de marketing.
_PATRONES = re.compile(
    r"(\d+\s*%"  # 90%
    r"|\b\d+(?:[.,]\d+)?\s*[x×]\b"  # 10x, 3.5x
    r"|\$\s?\d"  # $252
    r"|\b\d+(?:[.,]\d+)?\s*(?:billion|millones|millardos|mil\s+millones|m€|b)\b"  # 252 millones
    r"|\bmejor que\b|\bsupera\b|\bel mejor\b|\brevoluciona|\bstate[- ]of[- ]the[- ]art|\bsota\b)",
    re.IGNORECASE,
)
_MARCA = "⚠️ sin verificar"


def afirmacion_sin_verificar(texto: str) -> bool:
    """True si el texto contiene una cifra/multiplicador/superlativo de marketing (a verificar)."""
    return bool(_PATRONES.search(texto or ""))


def higienizar(necesidades: list[Necesidad]) -> list[Necesidad]:
    """Marca los hallazgos de la RED con afirmaciones numéricas/superlativas como 'sin verificar' y
    baja su prioridad (no ascienden por hype). Idempotente: no re-marca lo ya marcado. Devuelve la
    misma lista (mutando in place las de la Red que lo necesiten)."""
    for n in necesidades:
        if n.fuente != Fuente.RED or _MARCA in n.titulo:
            continue
        texto = n.titulo + " " + " ".join(n.evidencia)
        if afirmacion_sin_verificar(texto):
            n.titulo = f"{_MARCA}: {n.titulo}"
            n.descripcion = (
                n.descripcion + " Exige fuente primaria + prueba antes de adoptar (no por hype)."
            ).strip()
            n.prioridad = max(1, n.prioridad - 1)
    return necesidades
