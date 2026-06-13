"""
gepa_pareto.py — frontera de Pareto para GEPA (selección de candidatos por instancia, no por media).

El bucle de `gepa.py` guarda UN solo «mejor» por score AGREGADO. GEPA real (Agrawal et al. 2025,
"GEPA: Reflective Prompt Evolution Can Outperform Reinforcement Learning", arXiv:2507.19457) mantiene
una FRONTERA de candidatos: un candidato sobrevive si NADIE lo domina (≥ en todas las instancias y >
en al menos una). Para mutar el siguiente, GEPA muestrea de la frontera ponderando por cuántas
instancias «gana» cada candidato — así NO se queda atascado en un óptimo local de la media y conserva
estrategias COMPLEMENTARIAS (uno bueno en F2, otro bueno en F7) que la media fusionaría y perdería.

Aquí vive esa pieza, PURA y DETERMINISTA, fuera de `gepa.py` a propósito: ese fichero está en deuda de
tamaño (>400 líneas, ratchet de la Brújula) y NO puede engordar. El cableado dentro de
`optimizar_prompt` (sustituir el «mejor» único por la frontera) es 🟠 DECLARADO (D-97): se hará al
partir `gepa.py`, sin engordarlo. Sin red, sin LM Studio: testeable con vectores de score.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Tolerancia para comparar scores en coma flotante (dos scores dentro de esto se tratan como iguales).
_TOL = 1e-9


@dataclass
class CandidatoPareto:
    """Un candidato de prompt con su VECTOR de score por instancia (id de escenario → score 0..1)."""

    clave: str
    vector: dict[str, float] = field(default_factory=dict)
    prompt: str = ""


def vector_de(detalle: list[dict]) -> dict[str, float]:
    """Construye el vector por instancia a partir del `detalle` de `gepa.evaluar`
    (lista de `{"id":…, "ok": bool}`): id → 1.0 si pasó, 0.0 si no."""
    return {str(d.get("id", i)): (1.0 if d.get("ok") else 0.0) for i, d in enumerate(detalle)}


def agregado(vector: dict[str, float]) -> float:
    """Score AGREGADO (media) — el que usa hoy `gepa.py`. Útil como desempate."""
    return sum(vector.values()) / len(vector) if vector else 0.0


def domina(a: dict[str, float], b: dict[str, float]) -> bool:
    """True si `a` DOMINA a `b` (Pareto): a ≥ b en TODAS las instancias y a > b en AL MENOS una.
    Compara sobre la unión de instancias (ausente = 0.0)."""
    claves = set(a) | set(b)
    if not claves:
        return False
    mejor_en_alguna = False
    for k in claves:
        va, vb = a.get(k, 0.0), b.get(k, 0.0)
        if va < vb - _TOL:
            return False  # peor en alguna → no domina
        if va > vb + _TOL:
            mejor_en_alguna = True
    return mejor_en_alguna


def frontera_pareto(candidatos: list[CandidatoPareto]) -> list[CandidatoPareto]:
    """La frontera: candidatos a los que NADIE domina. Preserva estrategias complementarias."""
    return [
        c
        for c in candidatos
        if not any(o is not c and domina(o.vector, c.vector) for o in candidatos)
    ]


def instancias_ganadas(cand: CandidatoPareto, candidatos: list[CandidatoPareto]) -> set[str]:
    """Instancias en las que `cand` alcanza el MÁXIMO de la columna (las que «gana»)."""
    ganadas: set[str] = set()
    for k, v in cand.vector.items():
        techo = max((o.vector.get(k, 0.0) for o in candidatos), default=0.0)
        if v >= techo - _TOL and v > 0.0:
            ganadas.add(k)
    return ganadas


def pesos_de_frontera(candidatos: list[CandidatoPareto]) -> list[tuple[CandidatoPareto, int]]:
    """Frontera con su PESO = nº de instancias que gana cada candidato. Un sampler con RNG muestrearía
    el siguiente padre a mutar ponderando por este peso (lo que hace GEPA)."""
    frontera = frontera_pareto(candidatos)
    return [(c, len(instancias_ganadas(c, candidatos))) for c in frontera]


def elegir_de_frontera(candidatos: list[CandidatoPareto]) -> CandidatoPareto | None:
    """Elige DETERMINISTAMENTE el siguiente candidato a expandir de la frontera: el que gana MÁS
    instancias (mayor cobertura), desempatando por score agregado y luego por `clave` (estable, sin RNG
    — el muestreo estocástico ponderado de GEPA queda como `pesos_de_frontera` para quien tenga semilla).
    """
    pesos = pesos_de_frontera(candidatos)
    if not pesos:
        return None
    return max(pesos, key=lambda cp: (cp[1], agregado(cp[0].vector), cp[0].clave))[0]
