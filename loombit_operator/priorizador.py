"""
priorizador.py — ordena los hilos del telar de forma DETERMINISTA. Núcleo blanco.

Aplica la fórmula de Generative Agents (Park et al., 2023): cada hilo se puntúa con
`recency · importance · relevance`, combinadas como media ponderada de tres componentes
normalizados a 0..1. El ORDEN lo decide CÓDIGO (no el LLM):

  - recency    = urgencia EN EL TIEMPO: un plazo vencido/hoy pesa lo máximo, uno lejano decae.
  - importance = importancia de dominio (1..3, la fija código en `comprension`/cobros, no el LLM).
  - relevance  = lo que el usuario suele atender → la aportan sus HÁBITOS (`habitos.py`): sube lo
                 que "sueles aceptar", baja lo que "sueles ignorar". Neutro (0.5) si no hay patrón.

Así el telar ANTICIPA y prioriza según tu comportamiento, sin que ninguna cifra la invente el LLM
y sin que nada salga de la máquina. Ver docs/INVESTIGACION_ASISTENTE_PROACTIVO_2026.md (#3).
"""

from __future__ import annotations

from typing import Any

# Pesos de los tres componentes. Generative Agents los usa a 1.0; aquí son afinables.
PESOS = {"recency": 1.0, "importance": 1.0, "relevance": 1.0}

# Vida media (días) del decaimiento de recency: a esta distancia, la urgencia temporal cae a la mitad.
VIDA_MEDIA_DIAS = 3.0


def recency_por_plazo(dias_hasta: float, vida_media: float = VIDA_MEDIA_DIAS) -> float:
    """Urgencia temporal 0..1 a partir de los días que faltan para el plazo. Vencido u hoy
    (`dias_hasta <= 0`) → 1.0; decae exponencialmente con los días futuros."""
    dias = max(0.0, float(dias_hasta))
    return round(0.5 ** (dias / vida_media), 4)


def normaliza_importancia(importancia: int) -> float:
    """Importancia de dominio (1..3) → 0..1. Clampa fuera de rango (no se inventa nada)."""
    imp = min(3, max(1, int(importancia)))
    return round(imp / 3, 4)


def puntuar(
    *,
    importancia: int,
    recency: float,
    relevancia: float,
    pesos: dict[str, float] | None = None,
) -> float:
    """Score 0..1 = media ponderada de importance·recency·relevance (todos ya 0..1)."""
    w = pesos or PESOS
    imp = normaliza_importancia(importancia)
    total = w["importance"] * imp + w["recency"] * recency + w["relevance"] * relevancia
    denom = w["importance"] + w["recency"] + w["relevance"]
    return round(total / denom, 4)


def _relevancia_de(hilo: dict[str, Any], habitos: Any) -> float:
    """Relevancia 0..1 desde los hábitos del usuario (0.5 neutro si no hay patrón ni datos)."""
    if habitos is None:
        return 0.5
    tipo = str(hilo.get("tipo", "") or "")
    sujeto = str(hilo.get("sujeto", hilo.get("contraparte", "")) or "")
    if not tipo or not sujeto:
        return 0.5
    try:
        return float(habitos.prioridad(tipo, sujeto))
    except Exception:
        return 0.5


def puntuar_hilo(hilo: dict[str, Any], habitos: Any = None) -> float:
    """Puntúa un hilo del telar leyendo sus campos best-effort: `urgencia`/`importancia` (1..3),
    `dias_hasta` (días al plazo; ausente → tratado como urgente=hoy), y `tipo`+`sujeto` para el
    hábito. Tolerante a hilos incompletos."""
    importancia = hilo.get("urgencia", hilo.get("importancia", 2))
    dias = hilo.get("dias_hasta")
    recency = recency_por_plazo(dias) if dias is not None else 1.0
    relevancia = _relevancia_de(hilo, habitos)
    return puntuar(importancia=importancia, recency=recency, relevancia=relevancia)


def ordenar(hilos: list[dict[str, Any]], habitos: Any = None) -> list[dict[str, Any]]:
    """Devuelve los hilos ordenados por prioridad descendente (estable). Anota cada hilo con su
    `score` para que la UI pueda mostrar/depurar el porqué. No pierde ni duplica hilos."""
    for h in hilos:
        h["score"] = puntuar_hilo(h, habitos)
    return sorted(hilos, key=lambda h: h["score"], reverse=True)
