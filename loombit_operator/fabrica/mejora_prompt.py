"""
mejora_prompt.py — RADAR ACTIVO (slice 1): mejora un prompt con panel multi-persona, MEDIDO.

El radar deja de ser solo guardián PASIVO (gate de frescura + centinela): aquí empieza el MOTOR
ACTIVO que mejora prompts. Patrón de la Ley Fundacional: el LLM (panel de personas) PROPONE una
versión mejor; el CÓDIGO mide antes/después sobre un eval y DISPONE — si no mejora de verdad, se
RECHAZA y se conserva el original. Deja un recibo de conducta `mejora_prompt` (D-70) que el gate ya
valida (antes_score/despues_score/eval/n_casos), así "mejoré el prompt" deja de ser palabra y pasa a
ser número.

Puro y testeable: el proponedor (LLM) y el evaluador (eval) entran como callables; la decisión es
determinista. NO duplica `fabrica/gepa.py` (búsqueda GEPA reflexiva sobre trazas + frontera de
Pareto): esto es la PRIMITIVA mínima 'propón → mide → dispón' reutilizable, con el panel
multi-persona (SPP) como proponedor y el recibo de conducta como prueba. Cablear un proponedor LLM
real y un eval real es el siguiente slice (necesita LM Studio + recibo EN VIVO; regla nº1).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ..conducta import exigir_recibo  # reusa el gate del recibo; no lo reinventa

# Panel CERRADO de personas (multi-persona / Solo Performance Prompting). "Cerrado" = roles de
# razonamiento fijos, no markup/JS libre: el panel PROPONE texto, nunca es camino de control (§SEG-8).
PERSONAS: tuple[str, ...] = (
    "Director creativo",
    "Ejecutivo de marketing",
    "Ingeniero de software",
)


def construir_brief_panel(original: str, objetivo: str) -> str:
    """Brief determinista que consumirá el LLM proponedor. Función PURA: el texto del encargo es
    testeable sin LLM. El LLM PROPONE; aquí solo preparamos su encargo (el panel cerrado de personas).
    """
    roles = " + ".join(PERSONAS)
    return (
        f"Mejora este prompt razonando como un panel de {roles} que dialoga y "
        f"converge en una sola versión.\n"
        f"Objetivo del prompt: {objetivo}\n"
        f"Devuelve SOLO el prompt mejorado, sin explicación ni comentarios.\n\n"
        f"--- PROMPT ORIGINAL ---\n{original}"
    )


@dataclass(frozen=True)
class ResultadoMejora:
    """Veredicto del radar activo: mejoró o no, con el prompt vigente y el recibo si mejoró."""

    mejoro: bool
    prompt: str  # el que queda vigente: el mejorado si mejoró, el original si se rechazó
    antes_score: float
    despues_score: float
    recibo: dict | None  # recibo de conducta `mejora_prompt` válido, o None si se rechazó
    motivo: str


def mejorar_prompt(
    original: str,
    objetivo: str,
    proponer: Callable[[str], str],
    evaluar: Callable[[str], float],
    n_casos: int,
    eval_nombre: str,
) -> ResultadoMejora:
    """Propón (panel) → mide (eval) → dispón (código). Devuelve el prompt vigente + recibo si mejoró.

    - `proponer(brief)`: el LLM (panel multi-persona) devuelve un candidato. Inyectado → testeable.
    - `evaluar(prompt)`: puntúa el prompt sobre el eval (el MISMO para antes y para después).
    - Si el candidato no supera al original, se RECHAZA y se conserva el original (el código dispone).
    - El recibo se valida con `conducta` (reuso del gate D-70): exige delta real y n_casos >= suelo;
      si no se cumple, `exigir_recibo` lanza `ReciboInvalido` — un "lo mejoré" sin número no cuenta.
    """
    antes = float(evaluar(original))
    candidato = proponer(construir_brief_panel(original, objetivo))
    despues = float(evaluar(candidato))
    if despues <= antes:
        return ResultadoMejora(
            mejoro=False,
            prompt=original,
            antes_score=antes,
            despues_score=despues,
            recibo=None,
            motivo=(
                f"el panel no mejoró el prompt (después {despues} <= antes {antes}): "
                f"se conserva el original"
            ),
        )
    recibo = exigir_recibo(
        {
            "tipo": "mejora_prompt",
            "antes_score": antes,
            "despues_score": despues,
            "eval": eval_nombre,
            "n_casos": n_casos,
        }
    )
    return ResultadoMejora(
        mejoro=True,
        prompt=candidato,
        antes_score=antes,
        despues_score=despues,
        recibo=recibo,
        motivo="el panel mejoró el prompt y el recibo de conducta lo respalda",
    )
