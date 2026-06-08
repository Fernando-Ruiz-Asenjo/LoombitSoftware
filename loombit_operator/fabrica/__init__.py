"""
Fábrica de Skills (Skill X) — auto-autoría GOBERNADA de tools/skills útiles.

Loombit detecta un hueco ÚTIL (no un micro-tweak), redacta una tool/skill nueva con el
modelo coder LOCAL, la valida con un arnés grado-foso (seguridad AST + black + ruff +
import aislado + evals + sin regresión) y la PROPONE con gate — NUNCA la auto-aplica.
Es el patrón DGM/SICA/ADAS en su versión segura: evolucionamos el ANDAMIAJE (código,
prompts, manifests), nunca los pesos; con archivo/linaje y recompensa verificable.

Brújula: cognición no extracción · acierta al 100 % · cero fallos · no mentir (DoD) ·
blanco · el gate de aprobación es sagrado. Ver `docs/FABRICA_DE_SKILLS.md`.
"""

from __future__ import annotations

from .seguridad import ResultadoSeguridad, analizar_seguridad

__all__ = ["ResultadoSeguridad", "analizar_seguridad"]
